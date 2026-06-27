from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Payment, PaymentStatus, User, PaymentMethod
from datetime import datetime
from fastapi import Depends, BackgroundTasks
import httpx
import asyncio
import os
from app.services.kashier_manager import verify_kashier_webhook
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

async def send_n8n_webhook(payload: dict):
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("⚠️ N8N_WEBHOOK_URL not configured — skipping notification")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=10.0)
            logger.info("✅ Successfully sent webhook to N8N")
    except Exception as e:
        logger.error("❌ Failed to send N8N webhook: %s", e)

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

    # 1. Extract hash (Kashier may send it as 'hash' or 'signature')
    received_hash = body.get("hash", "") or body.get("signature", "")
    logger.info("🔍 Received Hash: %s", received_hash)

    data = body.get("data", {})
    if not data:
        data = dict(body)

    # 2. Strip hash/signature keys from data before verification
    data.pop("hash", None)
    data.pop("signature", None)

    # 3. Verify signature — reject if missing OR invalid
    if not received_hash:
        logger.error("🚨 Kashier webhook missing signature! Possible spoofing attempt.")
        raise HTTPException(status_code=401, detail="Missing signature")
    if not verify_kashier_webhook(data, received_hash):
        logger.error("🚨 Kashier webhook signature mismatch! hash=%s", received_hash)
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
            logger.info("🔍 FULL BODY for missing payment: %s", body)
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

        if payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CONFIRMED
            payment.confirmed_at = datetime.utcnow()
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                # Determine subscription length from plan_key
                days = 30
                sub_type = "1_month"
                if payment.plan_key:
                    if "yearly" in payment.plan_key:
                        days = 365
                        sub_type = "1_year"
                    elif "quarterly" in payment.plan_key:
                        days = 90
                        sub_type = "3_months"
                

                
                # Set subscription end date based on plan (30 / 90 / 365 days)
                user.end_at = datetime.utcnow() + timedelta(days=days)
                user.is_active = True
            
            db.commit()
            logger.info("✅ Payment CONFIRMED for order %s | user %s", order_id, payment.user_id)
            
            # Send webhook to N8N
            duration_type = "1_month"
            if payment.plan_key:
                if "yearly" in payment.plan_key:
                    duration_type = "1_year"
                elif "quarterly" in payment.plan_key:
                    duration_type = "3_months"

            payload = {
                "user_id": user.id if user else payment.user_id,
                "user_name": getattr(user, "full_name", "") if user else "",
                "user_email": getattr(user, "email", "") if user else "",
                "user_phone": getattr(user, "phone", "") if user else "",
                "amount": float(payment.amount) if payment.amount else 0.0,
                "currency": payment.currency,
                "order_id": order_id,
                "transaction_id": data.get("transactionId", ""),
                "payment_status": "success",
                "payment_method": "kashier",
                "paid_at": payment.confirmed_at.isoformat() if payment.confirmed_at else datetime.utcnow().isoformat(),
                "subscription_duration": duration_type
            }
            background_tasks.add_task(send_n8n_webhook, payload)
        else:
            logger.info("ℹ️ Payment already %s — skipping", payment.status)
    
    return {"status": "ok"}