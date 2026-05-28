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

# ─── Kashier: إنشاء أوردر ────────────────────────────────────
@router.post("/kashier/create")
def kashier_create(data: KashierCreateOrder, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order_id = f"ORD-{current_user.id}-{uuid.uuid4().hex[:8].upper()}"

    result = create_kashier_payment_url(
        order_id=order_id,
        amount=data.amount,
        currency=data.currency,
        user_email=current_user.email,
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
def kashier_success(orderId: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(
        Payment.method == PaymentMethod.KASHIER,
        Payment.provider_order_id == orderId,
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
