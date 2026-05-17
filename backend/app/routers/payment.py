from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import os
from datetime import datetime
from app.models import Payment, PaymentMethod, PaymentStatus, User
from app.schemas import PayPalCreateOrder, PayPalOrderOut, PaymentOut, KashierCreateOrder, KashierOrderOut
from app.services.paypal import create_paypal_order, capture_paypal_order
from app.routers.users import get_current_user
from app.database import get_db

router = APIRouter(prefix="/payment", tags=["Payment"])

# ─── PayPal: إنشاء أوردر ─────────────────────────────────────
@router.post("/paypal/create", response_model=PayPalOrderOut)
async def paypal_create(data: PayPalCreateOrder, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = await create_paypal_order(data.amount, data.currency)
    
    payment = Payment(
        user_id=current_user.id,
        method=PaymentMethod.PAYPAL,
        amount=data.amount,
        currency=data.currency,
        paypal_order_id=result["order_id"],
        provider_order_id=result["order_id"],
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()
    
    return result

# ─── PayPal: بعد ما يرجع من PayPal ──────────────────────────
@router.get("/paypal/success")
async def paypal_success(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # token هنا هو order_id بيبعته PayPal في الـ return URL
    payment = db.query(Payment).filter(
        Payment.method == PaymentMethod.PAYPAL,
        Payment.user_id == current_user.id,
        or_(Payment.provider_order_id == token, Payment.paypal_order_id == token),
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="مش لاقي الأوردر")

    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    if payment.status == PaymentStatus.CONFIRMED:
        return RedirectResponse(url=f"{frontend_url}/onboarding.html")

    capture = await capture_paypal_order(token)
    
    if capture["status"] != "COMPLETED":
        raise HTTPException(status_code=400, detail="الدفع مش مكتمل")
    
    # تأكيد الدفع وتفعيل اليوزر
    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_at = datetime.utcnow()
    
    user = db.query(User).filter(User.id == payment.user_id).first()
    if user:
        user.is_active = True
    
    db.commit()
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/onboarding.html")

# ─── PayPal: إلغاء ───────────────────────────────────────────
@router.get("/paypal/cancel")
def paypal_cancel():
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/payment.html")

from app.services.kashier_manager import create_kashier_payment_url
import uuid

# ─── Kashier: إنشاء أوردر ────────────────────────────────────
@router.post("/kashier/create")
def kashier_create(data: KashierCreateOrder, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order_id = f"ORD-{current_user.id}-{uuid.uuid4().hex[:8].upper()}"

    result = create_kashier_payment_url(
        order_id=order_id,
        amount=data.amount,
        user_email=current_user.email,
        user_id=current_user.id,
    )

    payment = Payment(
        user_id=current_user.id,
        method=PaymentMethod.KASHIER,
        amount=data.amount,
        currency=data.currency,
        paypal_order_id=order_id,   # backward compatibility
        provider_order_id=order_id,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.commit()

    return result

# ─── Kashier: بعد ما يرجع من صفحة الدفع ─────────────────────
@router.get("/kashier/success")
def kashier_success(orderId: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(
        Payment.method == PaymentMethod.KASHIER,
        or_(Payment.provider_order_id == orderId, Payment.paypal_order_id == orderId),
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="الأوردر مش موجود")

    # الـ webhook هو اللي بيأكد فعلاً - الصفحة دي بس للـ redirect
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/onboarding.html")

# ─── Kashier: لو فشل الدفع ───────────────────────────────────
@router.get("/kashier/fail")
def kashier_fail():
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    return RedirectResponse(url=f"{frontend_url}/payment.html?error=failed")
