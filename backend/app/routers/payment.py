from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import os
from datetime import datetime
from app.models import Payment, PaymentMethod, PaymentStatus, User
from app.schemas import PaymentOut, KashierCreateOrder, KashierOrderOut
from app.routers.users import get_current_user
from app.database import get_db

router = APIRouter(prefix="/payment", tags=["Payment"])


from app.services.kashier_manager import create_kashier_payment_url
import uuid
import logging

logger = logging.getLogger(__name__)

# ─── Kashier: إنشاء أوردر ────────────────────────────────────
@router.post("/kashier/create")
async def kashier_create(data: KashierCreateOrder, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Delete old pending Kashier payments for this user so they don't pile up in the admin dashboard
    db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.method == PaymentMethod.KASHIER,
        Payment.status == PaymentStatus.PENDING
    ).delete(synchronize_session=False)
    db.commit()

    order_id = f"ORD-{current_user.id}-{uuid.uuid4().hex[:8].upper()}"

    result = await create_kashier_payment_url(
        order_id=order_id,
        amount=data.amount,
        currency=data.currency,
        user_email=current_user.email,
        user_phone=current_user.phone,
        user_id=current_user.id,
    )

    payment = Payment(
        user_id=current_user.id,
        method=PaymentMethod.KASHIER,
        amount=data.amount,
        currency=data.currency,
        provider_order_id=order_id,
        plan_key=data.plan_key,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()

    return result

# ─── Kashier: بعد ما يرجع من صفحة الدفع ─────────────────────
@router.get("/kashier/success")
def kashier_success(
    orderId: str = None,
    merchantOrderId: str = None,
    paymentStatus: str = None,
    db: Session = Depends(get_db)
):
    """
    Kashier بيبعت:
    - orderId = Kashier internal UUID
    - merchantOrderId = الـ order ID بتاعنا (ORD-56-XXXX)
    """
    # استخدم merchantOrderId الأول لأنه الـ ID بتاعنا
    lookup_id = merchantOrderId or orderId
    
    redirect_page = "onboarding.html"
    
    if lookup_id:
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.KASHIER,
            or_(
                Payment.provider_order_id == lookup_id,
                Payment.provider_order_id == orderId,
            )
        ).first()
        
        if payment:
            if payment.status == PaymentStatus.PENDING:
                # الـ webhook المفروض يكون وصل قبل كده
                # بس لو ما وصلش، نعمل confirm هنا كـ fallback
                logger.info("⚠️ Payment still PENDING at success redirect — webhook may be delayed")
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user and user.onboarding_completed:
                redirect_page = "dashboard.html"
    
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/{redirect_page}")

# ─── Kashier: لو فشل الدفع ───────────────────────────────────
@router.get("/kashier/fail")
def kashier_fail():
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/payment.html?error=failed")
