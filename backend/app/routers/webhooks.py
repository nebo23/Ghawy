from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Payment, PaymentStatus, User, PaymentMethod
from datetime import datetime
from fastapi import Depends
from app.services.kashier_manager import verify_kashier_webhook
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

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
            Payment.provider_order_id == order_id,
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
                card_token = (
                    body.get("cardToken") or 
                    body.get("card_token") or 
                    body.get("token") or
                    body.get("CardToken")
                )
                shopper_ref = (
                    body.get("shopperReference") or 
                    body.get("shopper_reference") or
                    body.get("ShopperReference")
                )

                if card_token:
                    if not user.card_token:
                        user.card_token = card_token
                        user.shopper_reference = shopper_ref
                        user.subscription_start = datetime.utcnow()
                        user.subscription_end = datetime.utcnow() + timedelta(days=30)
                        user.next_charge_at = datetime.utcnow() + timedelta(days=30)
                        user.last_charged_at = datetime.utcnow()
                        user.subscription_type = "monthly"
                        logger.info(
                            "✅ Token saved for user %s: %s...",
                            user.id, card_token[:8],
                        )
                else:
                    logger.warning(
                        "⚠️ No card token received for user %s | body keys: %s",
                        user.id, list(body.keys()),
                    )
                    logger.warning("Full body: %s", body)
 
            db.commit()
 
    return {"status": "ok"}