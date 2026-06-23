"""
Legacy Access Router
====================
Provides two endpoints for the legacy member free-month promo:

  POST /api/legacy/send-otp    — validate email & send 6-digit OTP
  POST /api/legacy/verify-otp  — verify OTP, create/update user, return JWT

OTP store is an in-memory dict (acceptable for 10-minute codes).
"""

import random
import time
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LegacyEmail, User
from app.routers.users import create_token, hash_password
from app.services.email_service import send_legacy_otp_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legacy", tags=["Legacy Access"])

# ─── In-memory OTP store ─────────────────────────────────────────────────────
# { email: { "code": "123456", "expires_at": <unix timestamp> } }
_otp_store: dict[str, dict] = {}

OTP_TTL_SECONDS = 600   # 10 minutes


def _clean_expired_otps():
    """Remove expired entries to keep the dict lean."""
    now = time.time()
    expired = [e for e, v in _otp_store.items() if v["expires_at"] < now]
    for e in expired:
        _otp_store.pop(e, None)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    full_name: str
    password: str


# ─── Endpoint 1: Send OTP ────────────────────────────────────────────────────

@router.post("/send-otp")
def send_otp(data: SendOTPRequest, db: Session = Depends(get_db)):
    email = data.email.lower().strip()

    # 1. Check legacy_emails table
    legacy_entry = db.query(LegacyEmail).filter(LegacyEmail.email == email).first()
    if not legacy_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="هذا البريد غير مؤهل للعرض"
        )

    # 2. Check if already redeemed
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user and existing_user.is_legacy_redeemed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="لقد استفدت بالفعل من هذا العرض"
        )

    # 3. Generate OTP
    _clean_expired_otps()
    code = f"{random.randint(0, 999999):06d}"
    _otp_store[email] = {
        "code": code,
        "expires_at": time.time() + OTP_TTL_SECONDS,
    }
    logger.info("Legacy OTP generated for %s: %s", email, code)

    # 4. Send email
    try:
        send_legacy_otp_email(email, code)
    except Exception as exc:
        logger.warning("Failed to send legacy OTP email to %s: %s", email, exc)

    return {"message": "تم إرسال كود التحقق على بريدك الإلكتروني"}


# ─── Endpoint 2: Verify OTP ──────────────────────────────────────────────────

@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    submitted_otp = data.otp.strip()
    full_name = data.full_name.strip()
    password = data.password

    # 1. Validate OTP
    store_entry = _otp_store.get(email)
    if not store_entry or store_entry["expires_at"] < time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الكود غير صحيح أو انتهت صلاحيته"
        )
    if store_entry["code"] != submitted_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الكود غير صحيح أو انتهت صلاحيته"
        )

    # 2. Get or create user
    user = db.query(User).filter(User.email == email).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    hashed_pwd = hash_password(password)

    if user is None:
        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hashed_pwd,
            is_active=True,
            is_verified=True,
            onboarding_completed=False,  # Must complete onboarding first
        )
        db.add(user)
        db.flush()   # get user.id before commit
    else:
        # Update existing inactive user
        user.full_name = full_name
        user.hashed_password = hashed_pwd
        user.onboarding_completed = False  # Must complete onboarding first

    # 3. Activate with 30-day free subscription
    user.is_active = True
    user.is_verified = True
    user.is_legacy_redeemed = True
    user.subscription_source = "legacy_promo"
    user.end_at = now + timedelta(days=30)

    db.commit()
    db.refresh(user)

    # 4. Remove OTP from store
    _otp_store.pop(email, None)

    # 5. Issue JWT (same helper used by /auth/login)
    token = create_token(user.id)

    return {
        "message": "تم التحقق بنجاح",
        "access_token": token,
        "redirect": "/onboarding.html",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url,
        },
    }
