"""
Birthday Gift Router
====================
إيميل عيد الميلاد بيبعت لينك فيه توكن موقّع (JWT). لما اليوزر يضغط على
الزرار بنسجّل طلب هدية pending (مش تفعيل فوري) — الطلب بيظهر للأدمن في
الـ Team Dashboard تحت Pending Requests، ولما يوافق عليه:
  1) الاشتراك بيتمدد 7 أيام (بنحرّك end_at للأمام) — مرة واحدة بس في
     السنة (guard: birthday_gift_year).
  2) بيوصل لليوزر DM تهنئة أوتوماتيك من أكونت محمد صلاح.

  GET  /api/birthday/claim?token=...          — يسجّل الطلب ويعمل redirect للفرونت
  GET  /api/birthday/claims?status=...        — (أدمن) قايمة الطلبات
  POST /api/birthday/claims/{id}/approve      — (أدمن) موافقة: تمديد + DM
  POST /api/birthday/claims/{id}/reject       — (أدمن) رفض

التوكن نفسه بيتعمل هنا (make_birthday_token) وبيستهلكه email_service وقت
بناء الإيميل — عشان صيغة التوكن تفضل في مكان واحد.
"""
import os
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    BirthdayGiftClaim,
    Channel,
    ChatMember,
    Message,
    ChannelType,
    MemberRole,
    MessageType,
)
from app.routers.users import get_current_user
from app.services.subscription_service import extend_subscription
from app.services.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/birthday", tags=["Birthday"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
GIFT_DAYS = 7
_PURPOSE = "birthday_gift"
_TOKEN_TTL_DAYS = 14  # اللينك صالح أسبوعين بعد عيد الميلاد

# الرسالة الأوتوماتيك اللي بتوصل لليوزر بعد الموافقة — من أكونت محمد صلاح
_SENDER_EMAIL = os.getenv("BIRTHDAY_DM_SENDER_EMAIL", "mosalah@ghawy.ai")
_CONGRATS_DM = (
    "مبروك يا بطل! 🎉 تم تفعيل 7 أيام مجاني على اشتراكك هدية عيد ميلادك 🎂\n"
    "كل سنة وانت طيب، استمتع بيهم وكمّل تعلم 🚀"
)


def make_birthday_token(user_id: int, year: int) -> str:
    """توكن موقّع بيربط الهدية باليوزر + سنة معيّنة (يمنع إعادة الاستخدام السنة الجاية)."""
    payload = {
        "sub": str(user_id),
        "purpose": _PURPOSE,
        "year": int(year),
        "exp": datetime.utcnow() + timedelta(days=_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")


def _redirect(status_flag: str) -> RedirectResponse:
    # 303 عشان يتحوّل لـ GET على الفرونت
    return RedirectResponse(
        url=f"{_frontend_url()}/profile-settings.html?gift={status_flag}",
        status_code=303,
    )


def _require_owner(current_user: User):
    """403 unless this staff member has the Pending Requests permission.

    Gift claims are reviewed in that same tab, so they ride its permission.
    """
    require_permission(current_user, "pending-requests")



# ─── 1) زرار الإيميل: تسجيل طلب pending ─────────────────────────────
@router.get("/claim")
def claim_birthday_gift(token: str = "", db: Session = Depends(get_db)):
    """يفكّ التوكن ويسجّل طلب هدية pending — idempotent لكل سنة."""
    if not token:
        return _redirect("invalid")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        logger.info("🎂 Birthday claim: invalid/expired token")
        return _redirect("invalid")

    if payload.get("purpose") != _PURPOSE:
        return _redirect("invalid")

    try:
        user_id = int(payload.get("sub"))
        year = int(payload.get("year"))
    except (TypeError, ValueError):
        return _redirect("invalid")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _redirect("invalid")

    # اتفعّلت قبل كده لنفس السنة؟ مفيش طلب تاني
    if user.birthday_gift_year == year:
        logger.info("🎂 Birthday gift already claimed for user_id=%s year=%s", user_id, year)
        return _redirect("birthday_used")

    existing = (
        db.query(BirthdayGiftClaim)
        .filter(BirthdayGiftClaim.user_id == user_id, BirthdayGiftClaim.year == year)
        .first()
    )
    if existing:
        # فيه طلب بالفعل — لو لسه pending نطمّنه إنه تحت التنفيذ، لو اتوافق
        # عليه فالهدية مفعّلة أصلاً، ولو اترفض منسجلش واحد جديد بصمت.
        if existing.status == "approved":
            return _redirect("birthday_used")
        return _redirect("birthday_pending")

    db.add(BirthdayGiftClaim(user_id=user_id, year=year, status="pending"))
    db.commit()
    logger.info("🎂 Birthday gift claim registered: user_id=%s year=%s (pending approval)", user_id, year)
    return _redirect("birthday_pending")


# ─── 2) (أدمن) قايمة الطلبات — بتظهر في Pending Requests ────────────
@router.get("/claims")
def list_birthday_claims(
    status: str = Query("pending"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_owner(current_user)

    q = db.query(BirthdayGiftClaim)
    if status and status != "all":
        q = q.filter(BirthdayGiftClaim.status == status)
    claims = q.order_by(BirthdayGiftClaim.created_at.desc()).limit(200).all()

    # بيانات اليوزرات دفعة واحدة (مفيش FK — بنربط في الـ app layer)
    user_ids = {c.user_id for c in claims}
    users = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    pending_count = (
        db.query(BirthdayGiftClaim).filter(BirthdayGiftClaim.status == "pending").count()
    )

    def to_dict(c: BirthdayGiftClaim) -> dict:
        u = users.get(c.user_id)
        return {
            "id": c.id,
            "user_id": c.user_id,
            "year": c.year,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "decided_at": c.decided_at.isoformat() if c.decided_at else None,
            "full_name": u.full_name if u else f"user #{c.user_id}",
            "email": u.email if u else None,
            "phone": getattr(u, "phone", None) if u else None,
            "avatar_url": u.avatar_url if u else None,
            "birth_date": u.birth_date.isoformat() if (u and u.birth_date) else None,
            "end_at": u.end_at.isoformat() if (u and u.end_at) else None,
        }

    return {"claims": [to_dict(c) for c in claims], "pending_count": pending_count}


# ─── 3) (أدمن) الموافقة: تمديد 7 أيام + DM تهنئة من محمد صلاح ────────
def _send_congrats_dm(db: Session, to_user: User) -> bool:
    """يبعت رسالة التهنئة في الـ DM من أكونت محمد صلاح (automation).
    بيعمل/يجيب قناة الـ dm بنفس منطق chat.py بالظبط (dm_{lower}_{higher}).
    الوصول لليوزر بيتم عبر الـ polling العادي بتاع البادجات — مش محتاجين WS هنا."""
    sender = db.query(User).filter(User.email == _SENDER_EMAIL).first()
    if not sender:
        sender = (
            db.query(User)
            .filter(User.is_admin == True, User.is_active == True)  # noqa: E712
            .order_by(User.id)
            .first()
        )
    if not sender or sender.id == to_user.id:
        logger.warning("🎂 Congrats DM skipped: no sender account found")
        return False

    ids = sorted([sender.id, to_user.id])
    dm_name = f"dm_{ids[0]}_{ids[1]}"

    ch = (
        db.query(Channel)
        .filter(Channel.name == dm_name, Channel.channel_type == ChannelType.DM)
        .first()
    )
    if not ch:
        ch = Channel(name=dm_name, channel_type=ChannelType.DM)
        db.add(ch)
        db.flush()  # ناخد ch.id من غير commit منفصل — كله في ترانزاكشن الموافقة
        db.add(ChatMember(channel_id=ch.id, user_id=sender.id, role=MemberRole.MEMBER))
        db.add(ChatMember(channel_id=ch.id, user_id=to_user.id, role=MemberRole.MEMBER))

    db.add(Message(
        channel_id=ch.id,
        sender_id=sender.id,
        content=_CONGRATS_DM,
        message_type=MessageType.TEXT,
    ))
    return True


@router.post("/claims/{claim_id}/approve")
def approve_birthday_claim(
    claim_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_owner(current_user)

    claim = db.query(BirthdayGiftClaim).filter(BirthdayGiftClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status != "pending":
        raise HTTPException(status_code=400, detail=f"Claim is already {claim.status}")

    user = db.query(User).filter(User.id == claim.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.birthday_gift_year == claim.year:
        # الهدية اتفعّلت من مسار تاني لنفس السنة — نقفل الطلب من غير تمديد تاني
        claim.status = "approved"
        claim.decided_at = datetime.utcnow()
        claim.decided_by = current_user.id
        db.commit()
        return {"ok": True, "detail": "already_gifted", "dm_sent": False}

    # نفس منطق تمديد الاشتراك المستخدم في payment_service: نبني من end_at
    # الحالي لو لسه شغال، وإلا من دلوقتي
    now = datetime.utcnow()
    extend_subscription(user, GIFT_DAYS, now=now)
    user.birthday_gift_year = claim.year

    claim.status = "approved"
    claim.decided_at = now
    claim.decided_by = current_user.id

    dm_sent = _send_congrats_dm(db, user)
    db.commit()

    logger.info(
        "🎂 Birthday gift approved by admin_id=%s: user_id=%s +%s days -> end_at=%s (dm_sent=%s)",
        current_user.id, user.id, GIFT_DAYS, user.end_at, dm_sent,
    )
    return {"ok": True, "new_end_at": user.end_at.isoformat(), "dm_sent": dm_sent}


# ─── 4) (أدمن) رفض الطلب ────────────────────────────────────────────
@router.post("/claims/{claim_id}/reject")
def reject_birthday_claim(
    claim_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_owner(current_user)

    claim = db.query(BirthdayGiftClaim).filter(BirthdayGiftClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status != "pending":
        raise HTTPException(status_code=400, detail=f"Claim is already {claim.status}")

    claim.status = "rejected"
    claim.decided_at = datetime.utcnow()
    claim.decided_by = current_user.id
    db.commit()
    return {"ok": True}
