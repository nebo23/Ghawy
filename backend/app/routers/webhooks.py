from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Payment, PaymentStatus, PaymentMethod
from fastapi import Depends, BackgroundTasks
import logging

from app.services.kashier_manager import verify_kashier_webhook
from app.services.payment_service import confirm_kashier_payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/kashier")
async def kashier_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    import json as _json
    from urllib.parse import parse_qs

    content_type = request.headers.get("content-type", "")
    raw_bytes = await request.body()
    raw_str = raw_bytes.decode("utf-8", errors="replace")
    logger.info("🔍 RAW KASHIER BODY: %s", raw_str)
    logger.info("🔍 Content-Type: %s", content_type)
    logger.info("🔍 x-kashier-signature header: %s", request.headers.get("x-kashier-signature", ""))

    body = {}
    try:
        if "application/json" in content_type:
            body = _json.loads(raw_bytes)
        elif "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(raw_str)
            body = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        else:
            # Try JSON first, fallback to form
            try:
                body = _json.loads(raw_bytes)
            except Exception:
                parsed = parse_qs(raw_str)
                body = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except Exception as e:
        logger.error("❌ Failed to parse body: %s", e)
        return {"status": "ok"}

    logger.info("🔍 PARSED BODY: %s", body)

    data = body.get("data", {})
    if not data:
        data = dict(body)

    # 1. The real validation signature is in the `x-kashier-signature` HTTP header
    #    (the body `hash` is a separate internal value and must NOT be trusted here).
    received_signature = request.headers.get("x-kashier-signature", "")

    # 2. Verify signature — reject if missing OR invalid
    if not received_signature:
        logger.error("🚨 Kashier webhook missing x-kashier-signature header! Possible spoofing.")
        raise HTTPException(status_code=401, detail="Missing signature")
    if not verify_kashier_webhook(data, received_signature):
        logger.error("🚨 Kashier webhook signature mismatch!")
        raise HTTPException(status_code=401, detail="Invalid signature")

    status = data.get("status", "")
    order_id = data.get("merchantOrderId") or data.get("orderId", "")

    logger.info("📋 Status: %s | OrderId: %s", status, order_id)

    if status == "SUCCESS" and order_id:
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.KASHIER,
            Payment.provider_order_id == order_id,
        ).first()

        if not payment:
            logger.warning("⚠️ Payment not found for order_id: %s", order_id)
            return {"status": "ok"}

        # 🔒 Verify amount and currency match what we stored at order creation
        webhook_amount_raw = data.get("amount") or data.get("totalAmount") or data.get("orderAmount")
        webhook_currency = (data.get("currency") or "").upper()

        if webhook_amount_raw is not None:
            try:
                webhook_amount = float(webhook_amount_raw)
                # Allow tiny float rounding tolerance (Kashier sometimes returns "3000.00")
                if abs(webhook_amount - float(payment.amount)) > 0.01:
                    logger.error(
                        "🚨 Amount mismatch! Stored=%s, Webhook=%s, Order=%s, User=%s",
                        payment.amount, webhook_amount, order_id, payment.user_id
                    )
                    raise HTTPException(status_code=400, detail="Amount mismatch")
            except (ValueError, TypeError):
                logger.error("🚨 Could not parse webhook amount: %s", webhook_amount_raw)
                raise HTTPException(status_code=400, detail="Invalid amount in webhook")

        if webhook_currency and webhook_currency != (payment.currency or "").upper():
            logger.error(
                "🚨 Currency mismatch! Stored=%s, Webhook=%s, Order=%s",
                payment.currency, webhook_currency, order_id
            )
            raise HTTPException(status_code=400, detail="Currency mismatch")

        confirm_kashier_payment(
            db, payment, source="webhook",
            background_tasks=background_tasks,
            transaction_id=data.get("transactionId", ""),
        )

    return {"status": "ok"}