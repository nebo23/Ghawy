"""
OTP Manager — WhatsApp Cloud API (Meta / Facebook Business)
بيبعت كود التحقق عبر WhatsApp ويخزنه في الـ DB علشان يتحقق منه

المتطلبات في .env:
  WA_ACCESS_TOKEN    — System User Token من Meta Business Suite
  WA_PHONE_NUMBER_ID — Phone Number ID من WhatsApp Manager
  WA_TEMPLATE_NAME   — اسم الـ Authentication Template (اللي اتوافق عليه من Meta)
  WA_TEMPLATE_LANG   — لغة الـ Template (مثلاً: ar أو en_US)
"""
import os
import re
import random
import string
import httpx
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ─── WhatsApp Cloud API ────────────────────────────────────
WA_API_VERSION = "v21.0"
WA_BASE_URL = "https://graph.facebook.com"


def normalize_phone(phone: str) -> str:
    """يحول أرقام الهاتف المصرية لصيغة دولية E.164"""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if cleaned.startswith("01") and len(cleaned) == 11:
        return "+20" + cleaned[1:]
    if re.match(r"^20\d{10}$", cleaned):
        return "+" + cleaned
    if not cleaned.startswith("+"):
        return "+" + cleaned
    return cleaned


def _generate_otp(length: int = 6) -> str:
    """يولد كود عشوائي من 6 أرقام"""
    return "".join(random.choices(string.digits, k=length))


def _send_whatsapp_otp(phone_e164: str, otp_code: str) -> tuple:
    """
    يبعت رسالة WhatsApp عبر Meta Cloud API بإستخدام الـ Template المعتمد.

    Template: ghawyphone (UTILITY, lang=en)
    Body: "استخدم *{{1}}* لإكمال خطوتك"
    """
    access_token = os.getenv("WA_ACCESS_TOKEN")
    phone_number_id = os.getenv("WA_PHONE_NUMBER_ID")
    template_name = os.getenv("WA_TEMPLATE_NAME", "ghawyphone")
    template_lang = os.getenv("WA_TEMPLATE_LANG", "en")

    if not access_token or not phone_number_id:
        logger.error("❌ WA_ACCESS_TOKEN أو WA_PHONE_NUMBER_ID مش موجودين في .env")
        return False, False

    url = f"{WA_BASE_URL}/{WA_API_VERSION}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # الـ template `phoneotp` عنده BODY فقط بـ {{1}} — POSITIONAL format
    # لازم نبعت parameter_name مع كل parameter عشان يتماشى مع الـ POSITIONAL format
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_e164.lstrip("+"),  # Meta بتاخد الرقم بدون +
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": otp_code, "parameter_name": "otp"}
                    ],
                }
            ],
        },
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)

        data = resp.json()

        if resp.status_code == 200 and "messages" in data:
            msg_id = data["messages"][0].get("id", "unknown")
            logger.info("✅ WhatsApp OTP sent to %s | msg_id: %s", phone_e164, msg_id)
            return True, False
        else:
            # لو الـ Template مش موجود أو غير معتمد
            error = data.get("error", {})
            err_code = error.get("code")
            err_msg = error.get("message", "Unknown error")

            if err_code in (132000, 132001):
                logger.error(
                    "❌ Template '%s' مش موجود أو لسه في انتظار الموافقة من Meta. "
                    "روح Meta Business Manager > WhatsApp > Message Templates "
                    "وتأكد إن الـ template اتوافق عليه (Approved).",
                    template_name,
                )
                return False, True  # (failed, is_template_error)
            elif err_code == 131030:
                logger.error(
                    "❌ الرقم %s مش موجود على WhatsApp أو غير مُفعَّل.",
                    phone_e164,
                )
            else:
                logger.error(
                    "❌ WhatsApp API error for %s | code=%s | msg=%s",
                    phone_e164, err_code, err_msg,
                )
            return False, False

    except httpx.RequestError as e:
        logger.error("❌ Network error sending WhatsApp OTP to %s: %s", phone_e164, e)
        return False, False


# ─── Public Interface ──────────────────────────────────────

async def send_otp(phone: str, db: Session = None, user_id: int = None) -> bool:
    """
    يولد OTP ويبعته عبر WhatsApp ويخزنه في الـ DB.

    لو DEV_MODE=true أو الـ Template لسه مش موجود:
      - الكود بيتخزن في الـ DB
      - بيتطبع في الـ logs عشان تقدر تتستّ
      - الـ API بترجع نجاح عشان الـ frontend يكمل
    """
    phone_normalized = normalize_phone(phone)
    otp_code = _generate_otp()
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

    # إرسال عبر WhatsApp — sync httpx (up to 15s) so run it in a thread,
    # otherwise it blocks the single-worker event loop for the whole site
    from fastapi.concurrency import run_in_threadpool
    sent, is_template_error = await run_in_threadpool(_send_whatsapp_otp, phone_normalized, otp_code)

    # لو DEV_MODE أو template error: خزّن وطبع الكود في الـ logs
    if dev_mode or is_template_error:
        if is_template_error:
            logger.warning(
                "⚠️ DEV FALLBACK: Template غير موجود — الكود بيتطبع في الـ logs فقط."
                " اعمل Template معتمد في Meta Business Manager لتفعيل WhatsApp."
            )
        logger.warning(
            "🔑 [DEV OTP] رقم: %s | كود: %s | صالح لـ 10 دقايق",
            phone_normalized, otp_code
        )
        # خزّن في الـ DB عشان verify_otp يشتغل
        if db is not None:
            try:
                from app.models import PhoneOTP
                db.query(PhoneOTP).filter(PhoneOTP.phone == phone_normalized).delete()
                otp_record = PhoneOTP(
                    user_id=user_id,
                    phone=phone_normalized,
                    code=otp_code,
                    expires_at=datetime.utcnow() + timedelta(minutes=10),
                    is_used=False,
                )
                db.add(otp_record)
                db.commit()
            except Exception as e:
                logger.error("❌ Failed to save DEV OTP to DB: %s", e)
                return False
        return True  # نجاح للـ frontend

    if not sent:
        return False

    # حفظ الكود في الـ DB بعد الإرسال الناجح
    if db is not None:
        try:
            from app.models import PhoneOTP
            db.query(PhoneOTP).filter(PhoneOTP.phone == phone_normalized).delete()
            otp_record = PhoneOTP(
                user_id=user_id,
                phone=phone_normalized,
                code=otp_code,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
                is_used=False,
            )
            db.add(otp_record)
            db.commit()
            logger.info("💾 OTP saved to DB for %s", phone_normalized)
        except Exception as e:
            logger.error("❌ Failed to save OTP to DB for %s: %s", phone_normalized, e)

    return True


async def verify_otp(phone: str, code: str, db: Session = None) -> bool:
    """
    يتحقق من الكود المُدخَل مقارنةً بالكود المخزن في الـ DB.
    """
    phone_normalized = normalize_phone(phone)

    if db is None:
        logger.error("❌ DB session مش متاحة في verify_otp")
        return False

    try:
        from app.models import PhoneOTP

        otp_record = (
            db.query(PhoneOTP)
            .filter(
                PhoneOTP.phone == phone_normalized,
                PhoneOTP.code == code,
                PhoneOTP.is_used == False,
                PhoneOTP.expires_at >= datetime.utcnow(),
            )
            .order_by(PhoneOTP.created_at.desc())
            .first()
        )

        if otp_record is None:
            logger.warning(
                "❌ OTP مش صح أو انتهت صلاحيته للرقم %s", phone_normalized
            )
            return False

        # علّم الكود كمستخدَم
        otp_record.is_used = True
        db.commit()
        logger.info("✅ OTP verified for %s", phone_normalized)
        return True

    except Exception as e:
        logger.error("❌ OTP verification error for %s: %s", phone_normalized, e)
        return False
