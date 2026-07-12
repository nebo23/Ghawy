"""
Profile Router — User profile management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Channel, Message, MessageType, ChannelType, Post, Payment, PaymentStatus
from app.schemas import UserMemberOut, UserProfileUpdate, OnboardingUpdate
from app.routers.users import get_current_user, get_current_active_member, hash_password, verify_password
from pydantic import BaseModel
from typing import Optional
from fastapi import UploadFile, File
from datetime import datetime
import os
import uuid
import shutil
from datetime import datetime, timedelta
from app.services.otp_manager import send_otp, verify_otp
from app.models import PhoneOTP

router = APIRouter(prefix="/profile", tags=["Profile"])


# ─── Plan Labels (shared) ──────────────────────────────────
PLAN_LABELS = {
    "monthly_egp":   {"label": "شهري",       "amount": 10,   "currency": "EGP", "days": 30},
    "quarterly_egp": {"label": "تلت شهور",   "amount": 1200, "currency": "EGP", "days": 90},
    "yearly_egp":    {"label": "سنوي",        "amount": 3000, "currency": "EGP", "days": 365},
    "monthly_usd":   {"label": "Monthly",     "amount": 15,   "currency": "USD", "days": 30},
    "quarterly_usd": {"label": "Quarterly",   "amount": 35,   "currency": "USD", "days": 90},
    "yearly_usd":    {"label": "Yearly",      "amount": 100,  "currency": "USD", "days": 365},
}


# ─── Heartbeat ──────────────────────────────────────────────
@router.post("/heartbeat")
def heartbeat(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    current_user.last_seen = datetime.utcnow()
    db.commit()
    return {"ok": True}

@router.post("/offline")
def offline(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    current_user.last_seen = None
    db.commit()
    return {"ok": True}


# ─── Subscription Info ─────────────────────────────────────
@router.get("/subscription-info")
def get_subscription_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    بيرجع تفاصيل الاشتراك للمستخدم
    """
    # جيب آخر payment مدفوع للمستخدم
    last_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == PaymentStatus.CONFIRMED
    ).order_by(Payment.created_at.desc()).first()

    plan_key = (last_payment.plan_key if last_payment and last_payment.plan_key else None) or "monthly_egp"
    plan_info = PLAN_LABELS.get(plan_key, PLAN_LABELS["monthly_egp"])

    # حساب الـ days remaining من end_at
    days_remaining = None
    is_active = current_user.is_active
    subscription_end = current_user.end_at

    # حساب subscription_start من end_at - plan duration
    subscription_start = None
    if subscription_end:
        delta = subscription_end - datetime.utcnow()
        days_remaining = max(0, delta.days)
        subscription_start = subscription_end - timedelta(days=plan_info["days"])

    return {
        "is_active": is_active,
        "plan_key": plan_key,
        "plan_label": plan_info["label"],
        "amount": plan_info["amount"],
        "currency": plan_info["currency"],
        "subscription_start": subscription_start.isoformat() if subscription_start else None,
        "subscription_end": subscription_end.isoformat() if subscription_end else None,
        "days_remaining": days_remaining,
        "payment_method": last_payment.method.value if last_payment else None,
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


# ─── Get My Profile ─────────────────────────────────────────
@router.get("/me", response_model=UserMemberOut)
def get_my_profile(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Surface the auto-calculated video-watching streak so the profile card
    # and achievements section show it. Computed fresh, not persisted (no
    # commit), so it never overwrites anything in the DB.
    from app.services.progress_service import calculate_video_streak
    current_user.streak_days = calculate_video_streak(current_user.id, db)
    return current_user


# ─── Update My Profile ──────────────────────────────────────
@router.put("/me", response_model=UserMemberOut)
def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.bio is not None:
        current_user.bio = data.bio
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    if data.social_media_url is not None:
        current_user.social_media_url = data.social_media_url
    if data.show_social_media is not None:
        current_user.show_social_media = data.show_social_media

    db.commit()
    db.refresh(current_user)
    return current_user


# ─── Avatar image optimization ─────────────────────────────
AVATAR_MAX_DIM = 512

def optimize_avatar(filepath: str) -> None:
    """Downscale + recompress an uploaded avatar in place.

    Avatars render at ≤80px but users upload multi-MB camera photos; a raw
    2.5MB PNG was being shipped to every chat/member-list viewer.
    Best-effort: on any failure the original file is kept as-is.
    """
    try:
        from PIL import Image, ImageOps
        with Image.open(filepath) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((AVATAR_MAX_DIM, AVATAR_MAX_DIM), Image.LANCZOS)
            fmt = (img.format or "").upper()
            if filepath.lower().endswith((".jpg", ".jpeg")):
                img.convert("RGB").save(filepath, "JPEG", quality=85, optimize=True)
            elif filepath.lower().endswith(".webp"):
                img.save(filepath, "WEBP", quality=85)
            else:
                img.save(filepath, optimize=True)
    except Exception:
        pass


# ─── Upload Avatar ─────────────────────────────────────────
@router.post("/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Create directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    optimize_avatar(filepath)

    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)

    return {"avatar_url": avatar_url}


# ─── Onboarding Status ────────────────────────────────────
@router.get("/onboarding-status")
def get_onboarding_status(current_user: User = Depends(get_current_active_member)):
    return {"onboarding_completed": bool(current_user.onboarding_completed)}


# ─── Complete Onboarding ──────────────────────────────────
@router.post("/complete-onboarding")
def complete_onboarding(
    data: OnboardingUpdate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Update birth_date
    if data.birth_date:
        try:
            parts = data.birth_date.split("/")
            if len(parts) == 3:
                from datetime import date as date_type
                current_user.birth_date = date_type(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass  # skip invalid date

    # Update social media
    if data.social_media_url:
        current_user.social_media_url = data.social_media_url

    # Update avatar
    if data.avatar_url:
        current_user.avatar_url = data.avatar_url
    if data.selected_avatar:
        current_user.selected_avatar = data.selected_avatar
        # Auto-set avatar_url from preset if no upload was provided
        if not data.avatar_url:
            current_user.avatar_url = f"https://ghawy.ai/imgs/avatars/{data.selected_avatar}"

    # Mark onboarding as completed
    current_user.onboarding_completed = True
    db.commit()

    # Create "Start Here" welcome message
    start_here_ch = db.query(Channel).filter(Channel.name == "start-here").first()
    if start_here_ch:
        welcome_msg = Message(
            channel_id=start_here_ch.id,
            sender_id=current_user.id,
            content="Welcome to Ghawy! 🎉 Start by watching the introductory video in the Start Here section.",
            message_type=MessageType.TEXT,
        )
        db.add(welcome_msg)
        db.commit()

    return {"success": True, "redirect": "dashboard.html"}


# ─── Upload Avatar (Onboarding) ──────────────────────────
@router.post("/upload-avatar")
def upload_avatar_onboarding(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP files allowed")

    # Check file size (5MB max)
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 5MB")

    # Save to static/avatars
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "avatars")
    os.makedirs(static_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"{current_user.id}{ext}"
    filepath = os.path.join(static_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    optimize_avatar(filepath)

    avatar_url = f"/static/avatars/{filename}"
    current_user.avatar_url = avatar_url
    db.commit()

    return {"avatar_url": avatar_url}


# ─── Get Public Profile ────────────────────────────────────
@router.get("/{user_id}/public")
def get_public_profile(
    user_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Username from email
    username = user.email.split("@")[0] if user.email else "user"

    # Joined date
    months_en = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                 7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
    joined_at = ""
    if user.created_at:
        joined_at = f"Joined {months_en.get(user.created_at.month, '')} {user.created_at.year}"

    # Online status (heartbeat-based: last_seen within 60 seconds)
    is_online = False
    if user.last_seen is not None:
        is_online = (datetime.utcnow() - user.last_seen).total_seconds() < 60

    # Post count (community posts by this user)
    post_count = db.query(Post).filter(Post.user_id == user_id).count()

    # Live day-streak. The stored `streak_days` column is only refreshed when a
    # user opens their OWN profile, so for anyone else it is stale/0 — compute it
    # fresh here so the profile panel's "Day Streak" always reflects reality.
    from app.services.progress_service import calculate_video_streak
    streak_days = calculate_video_streak(user_id, db)

    # Achievement unlock flags for the viewed member (shared with dashboard).
    from app.routers.dashboard import compute_user_achievements
    achievements = compute_user_achievements(user_id, db)

    return {
        "id": user.id,
        "full_name": user.full_name,
        "username": username,
        "avatar_url": user.avatar_url,
        "selected_avatar": getattr(user, "selected_avatar", None),
        "bio": user.bio,
        "social_media_url": getattr(user, "social_media_url", None) if getattr(user, "show_social_media", True) else None,
        "show_social_media": getattr(user, "show_social_media", True),
        "level": getattr(user, "level", 1) or 1,
        "xp": getattr(user, "xp", 0) or 0,
        "badge": getattr(user, "badge", "Member") or "Member",
        "streak_days": streak_days,
        "joined_at": joined_at,
        "post_count": post_count,
        "is_online": is_online,
        "is_admin": user.is_admin,
        "custom_title": user.custom_title or "",
        **achievements,
    }


# ─── Get Any Member Profile ────────────────────────────────
@router.get("/{user_id}", response_model=UserMemberOut)
def get_member_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ─── Change Password ────────────────────────────────────────
@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords don't match")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password too short")

    # Google users can't change password
    if current_user.hashed_password.startswith("google_oauth_"):
        raise HTTPException(status_code=400, detail="Google accounts can't change password")

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is wrong")

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ─── Phone Verification (Vonage) ────────────────────────────
from app.schemas import SendPhoneOTP, VerifyPhoneOTP

@router.post("/send-phone-otp")
async def send_phone_otp(
    req: SendPhoneOTP,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """
    يبعت OTP على الرقم المدخل
    """
    import re as _re
    phone = req.phone.strip()

    # Accept Egyptian local format (01XXXXXXXXX) OR international E.164 (+XXXXXXXXXXX)
    # E.164: starts with +, followed by 7–15 digits (ITU-T E.164 standard)
    _cleaned = _re.sub(r'[\s\-\(\)]', '', phone)
    _is_egypt_local = _cleaned.startswith('01') and len(_cleaned) == 11 and _cleaned.isdigit()
    _is_e164 = bool(_re.match(r'^\+\d{7,15}$', _cleaned))
    if not (_is_egypt_local or _is_e164):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    # Use the cleaned version for the rest of the function
    phone = _cleaned

    # Check if number is used
    existing = db.query(User).filter(
        User.phone == phone,
        User.id != current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This number is registered to another account")

    success = await send_otp(phone, db=db, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send code, try again")

    return {"message": "Code sent to your number"}


@router.post("/verify-phone-otp")
async def verify_phone_otp(
    req: VerifyPhoneOTP,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """
    يتحقق من الكود ويحفظ الرقم في الـ DB
    """
    success = await verify_otp(req.phone, req.code, db=db)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid code or expired")

    # Save number
    current_user.phone = req.phone
    db.commit()

    return {"message": "Phone verified successfully ✅"}
