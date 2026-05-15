from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Payment, PaymentStatus, User, PaymentMethod
from datetime import datetime
from fastapi import Depends
from app.services.kashier_manager import verify_kashier_webhook
from app.services.paypal import verify_paypal_webhook
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# ─── PayPal Webhook ──────────────────────────────────────────
# PayPal بيبعت هنا تأكيد تلقائي لما يتم الدفع
@router.post("/paypal")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    headers = {k.lower(): v for k, v in request.headers.items()}

    is_valid = await verify_paypal_webhook(headers, body)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature")
    
    event_type = body.get("event_type")

    # Only activate user after a completed event (capture/checkout completion), not approval.
    order_id = None
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        order_id = (
            body.get("resource", {})
            .get("supplementary_data", {})
            .get("related_ids", {})
            .get("order_id")
        )
    elif event_type == "CHECKOUT.ORDER.COMPLETED":
        order_id = body.get("resource", {}).get("id")

    if order_id:
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.PAYPAL,
            or_(Payment.provider_order_id == order_id, Payment.paypal_order_id == order_id),
        ).first()
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CONFIRMED
            payment.confirmed_at = datetime.utcnow()
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                user.is_active = True
            
            db.commit()
    
    return {"status": "ok"}

@router.post("/kashier")
async def kashier_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
 
    # تحقق من صحة الـ signature
    received_sig = request.headers.get("x-kashier-signature", "")
    if not verify_kashier_webhook(body, received_sig):
        raise HTTPException(status_code=400, detail="Signature غير صالح")
 
    status = body.get("status", "")
    order_id = body.get("orderId", "")
 
    if status == "SUCCESS":
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.KASHIER,
            or_(Payment.provider_order_id == order_id, Payment.paypal_order_id == order_id),
        ).first()
 
        if payment and payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CONFIRMED
            payment.confirmed_at = datetime.utcnow()
            payment.is_recurring = False
            payment.recurring_cycle = 0
 
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                user.is_active = True

                # ── Save card token for recurring (first payment only) ──
                card_token = body.get("cardToken") or body.get("card_token")
                shopper_ref = body.get("shopperReference") or body.get("shopper_reference")

                if card_token and not user.card_token:
                    user.card_token = card_token
                    user.shopper_reference = shopper_ref
                    user.subscription_start = datetime.utcnow()
                    user.subscription_end = datetime.utcnow() + timedelta(days=30)
                    user.next_charge_at = datetime.utcnow() + timedelta(days=30)
                    user.last_charged_at = datetime.utcnow()
                    logger.info(
                        "✅ Token saved for user %s: %s...",
                        user.id, card_token[:10],
                    )
                else:
                    logger.warning(
                        "⚠️ No card token received for user %s | body keys: %s",
                        user.id, list(body.keys()),
                    )
 
            db.commit()
 
    return {"status": "ok"}