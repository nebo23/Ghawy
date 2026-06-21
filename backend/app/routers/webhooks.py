from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Payment, PaymentStatus, User, PaymentMethod
from datetime import datetime
from fastapi import Depends, BackgroundTasks
import httpx
import asyncio
from app.services.kashier_manager import verify_kashier_webhook
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

async def send_n8n_webhook(payload: dict):
    webhook_url = "https://n8n-vrtt.srv1552612.hstgr.cloud/webhook/d805c676-599f-43f5-b7f9-2a400e16d811"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=10.0)
            logger.info("✅ Successfully sent webhook to N8N")
    except Exception as e:
        logger.error("❌ Failed to send N8N webhook: %s", e)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/kashier")
async def kashier_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.json()
    
    logger.info("📦 Kashier webhook received: %s", body)
    
    received_hash = body.get("hash", "")
    data = body.get("data", {})
    
    if not data:
        data = body
    
    if received_hash and not verify_kashier_webhook(data, received_hash):
        logger.error("🚨 Webhook signature mismatch. Possible spoofing attempt!")
        raise HTTPException(status_code=400, detail="Invalid webhook signature") # 🛑 إيقاف التنفيذ فوراً لتجنب تفعيل اشتراك وهمي (حماية من ثغرة تجاوز التوقيع)
    
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