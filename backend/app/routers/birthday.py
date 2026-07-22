"""
Birthday Gift Router
====================
إيميل عيد الميلاد بيبعت لينك فيه توكن موقّع (JWT). لما اليوزر يضغط على
الزرار بنمدّد اشتراكه 7 أيام مجاناً على باقته الحالية (بنحرّك end_at
للأمام) — مرة واحدة بس في السنة (guard: birthday_gift_year).

  GET /api/birthday/claim?token=...  — يفعّل الهدية ويعمل redirect للفرونت

التوكن نفسه بيتعمل هنا (make_birthday_token) وبيستهلكه email_service وقت
بناء الإيميل — عشان صيغة التوكن تفضل في مكان واحد.
"""
import os
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/birthday", tags=["Birthday"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
GIFT_DAYS = 7
_PURPOSE = "birthday_gift"
_TOKEN_TTL_DAYS = 14  # اللينك صالح أسبوعين بعد عيد الميلاد


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


@router.get("/claim")
def claim_birthday_gift(token: str = "", db: Session = Depends(get_db)):
    """يفكّ التوكن ويمدّد الاشتراك 7 أيام — idempotent لكل سنة."""
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

    # اتفعّلت قبل كده لنفس السنة؟ منمددش تاني
    if user.birthday_gift_year == year:
        logger.info("🎂 Birthday gift already claimed for user_id=%s year=%s", user_id, year)
        return _redirect("birthday_used")

    # نفس منطق تمديد الاشتراك المستخدم في payment_service: نبني من end_at
    # الحالي لو لسه شغال، وإلا من دلوقتي
    now = datetime.utcnow()
    base = user.end_at if (user.end_at and user.end_at > now) else now
    user.end_at = base + timedelta(days=GIFT_DAYS)
    user.is_active = True
    user.birthday_gift_year = year
    db.commit()

    logger.info(
        "🎂 Birthday gift applied: user_id=%s +%s days -> end_at=%s",
        user_id, GIFT_DAYS, user.end_at,
    )
    return _redirect("birthday_ok")
