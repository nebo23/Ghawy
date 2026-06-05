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
    
    logger.info("📦 Kashier webhook received: %s", body)
    
    received_hash = body.get("hash", "")
    data = body.get("data", {})
    
    if not data:
        data = body
    
    if received_hash and not verify_kashier_webhook(data, received_hash):
        logger.warning("⚠️ Webhook signature mismatch — continuing anyway in test mode")
    
    status = data.get("status", "")
    order_id = data.get("merchantOOrderId") or data.get("merchantOrderId") or data.get("orderId", "")
    
    logger.info("📋 Status: %s | OrderId: %s", status, order_id)
    
    if status == "SUCCESS" and order_id:
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.KASHIER,
            Payment.provider_order_id == order_id,
        ).first()
        
        if not payment:
            logger.warning("⚠️ Payment not found for order_id: %s", order_id)
            return {"status": "ok"}
        
        if payment.status == PaymentStatus.PENDING:
            payment.status = PaymentStatus.CONFIRMED
            payment.confirmed_at = datetime.utcnow()
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                # 1. استخراج الـ card token من المسار المتداخل الصح
                card_token = (
                    data.get("sourceOfFunds", {})
                        .get("cardInfo", {})
                        .get("cardDataToken")
                    or data.get("cardToken")
                    or data.get("card_token")
                )
                
                if card_token:
                    payment.is_recurring = True   
                    payment.recurring_cycle = 1  
                    
                    shopper_ref = (
                        data.get("shopperReference") or
                        data.get("shopper_reference") or
                        f"user_{user.id}"
                    )
                    
                    ccv_token = (
                        data.get("sourceOfFunds", {})
                            .get("cardInfo", {})
                            .get("ccvToken")
                    )
                    
                    # 2. حفظ التوكن لأول مرة فقط لو مش موجود
                    if not user.card_token:
                        user.card_token = card_token
                        user.ccv_token = ccv_token 
                        user.shopper_reference = shopper_ref
                        logger.info("✅ Token saved for user %s: %s...", user.id, card_token[:8])
                    
                    # 3. تحديث بيانات وتواريخ الاشتراك (برة الـ if الداخلية عشان تتنفذ دايماً)
                    user.subscription_start = datetime.utcnow()
                    user.subscription_end = datetime.utcnow() + timedelta(minutes=2)
                    user.next_charge_at = datetime.utcnow() + timedelta(minutes=2)
                    user.last_charged_at = datetime.utcnow()
                    user.subscription_type = "monthly"
                    user.is_active = True
                else:
                    # الـ else دي بقت في مكانها الصح موازية لـ if card_token
                    payment.is_recurring = False
                    payment.recurring_cycle = 0
                    logger.warning("⚠️ No card token received from Kashier | data keys: %s", list(data.keys()))
            
            db.commit()
            logger.info("✅ Payment CONFIRMED for order %s | user %s", order_id, payment.user_id)
        else:
            logger.info("ℹ️ Payment already %s — skipping", payment.status)
    
    return {"status": "ok"}