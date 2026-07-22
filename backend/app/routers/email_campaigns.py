"""
Owner-only Email Campaigns API — powers the "Emails" tab in the Team Dashboard.

مبني على محرك حملات غاوي (app.services.email_campaign_service) المدموج جوه الـ backend.
كل الـ endpoints للـ owner بس (require_owner). الجمهور بييجي من الداتابيز الحية.

قواعد الأمان (متطابقة مع send_dynamic.py / send_campaign.py في مشروع Salah):
  • الوضع الافتراضي دايماً test — بيبعت بس على test_emails (مش لأي عضو حقيقي).
  • الإرسال الحقيقي (mode="real") لازم confirm_phrase == "GHAWY-OFFICIAL-SEND" بالظبط، وإلا 400.
  • التأخير العشوائي بين الإيميلات محفوظ في المحرك (rate-limit عشان Gmail).

ملاحظة معمارية مهمة:
  الإرسال الحقيقي بيتنفّذ في **thread بالخلفية** مش جوه الـ request — لأن nginx بيقطع أي
  request على /api/ بعد 120 ثانية (proxy_read_timeout)، والـ workers async (uvicorn) فأي
  عملية blocking طويلة على الـ event loop بتجمّد الموقع كله. التست (إيميل/اتنين) بيتنفّذ
  synchronously في threadpool وبيرجّع النتيجة فوراً.
"""
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Payment, PaymentStatus, EmailCampaignSend
from app.routers.users import get_current_user
from app.routers.admin import require_owner
from app.services.email_service import _governorate_to_arabic
from app.services import email_campaign_service as ecs


logger = logging.getLogger("ghawy.email_campaigns")

router = APIRouter(prefix="/admin/email-campaigns", tags=["Email Campaigns"])

CONFIRM_PHRASE = "GHAWY-OFFICIAL-SEND"
MAX_RECIPIENTS = 20000  # حد أقصى للحماية من payload ضخم

# حارس تزامن: حملة حقيقية واحدة بس في نفس الوقت (Gmail ما بيحبش اتصالات متزامنة كتير +
# بيمنع الإرسال المزدوج لو الزرار اتضغط مرتين). محمي بـ _send_lock.
_send_lock = threading.Lock()
_active_send: Dict[str, Any] = {"running": False, "campaign_id": None, "total": 0, "started_at": None}


# ══════════════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════════════

class PreviewRequest(BaseModel):
    content: Dict[str, Any]
    sample: Optional[Dict[str, Any]] = None


class SendRequest(BaseModel):
    recipients: List[Dict[str, Any]] = []
    content: Dict[str, Any]
    campaign_id: Optional[str] = None
    mode: str = "test"
    confirm_phrase: Optional[str] = None
    test_emails: Optional[List[str]] = None


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def _age_from_birth(bd) -> str:
    if not bd:
        return ""
    today = date.today()
    return str(today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day)))


def _plan_group(plan_key: Optional[str]) -> str:
    """يرجّع مجموعة الباقة من plan_key (monthly_egp → monthly ...)."""
    if not plan_key:
        return ""
    pk = plan_key.lower()
    if "month" in pk:
        return "monthly"
    if "quarter" in pk:
        return "quarterly"
    if "year" in pk:
        return "yearly"
    return pk


def _serialize_recipient(u: User, plan_key: Optional[str]) -> Dict[str, Any]:
    """الحقول اللي المحرك (normalize_recipients) والداشبورد متوقعينها لكل عضو."""
    return {
        "id": u.id,
        "name": u.full_name or "",
        "email": u.email or "",
        "phone": u.phone or "",
        "country": u.country or "",
        "governorate": u.governorate or "",
        "governorate_ar": _governorate_to_arabic(u.governorate or "") or "",
        "name_ar": "",
        "country_ar": "",
        "age": _age_from_birth(u.birth_date),
        "plan": plan_key or "",
        "plan_group": _plan_group(plan_key),
        "is_active": bool(u.is_active),
        "end_at": u.end_at.isoformat() if u.end_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ══════════════════════════════════════════════════════════════
#  GET /recipients — الجمهور المرشّح من الداتابيز الحية (بفلاتر)
# ══════════════════════════════════════════════════════════════

@router.get("/recipients")
def get_recipients(
    search: Optional[str] = Query(None, description="اسم أو إيميل"),
    country: Optional[str] = Query(None),
    governorate: Optional[str] = Query(None),
    status: str = Query("all", description="all | active | inactive"),
    plan: str = Query("all", description="all | monthly | quarterly | yearly | none"),
    expiring_days: Optional[int] = Query(None, ge=0, le=365, description="الاشتراكات اللي بتخلص خلال N يوم"),
    include_staff: bool = Query(False, description="ضمّ الأدمن/الأونر (افتراضي: مستبعدين)"),
    include_facets: bool = Query(True, description="رجّع قوائم البلاد/المحافظات للفلاتر"),
    limit: int = Query(MAX_RECIPIENTS, ge=1, le=MAX_RECIPIENTS),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    q = db.query(User)

    if not include_staff:
        q = q.filter(User.is_admin == False, User.is_owner == False)  # noqa: E712

    if search:
        term = f"%{search.strip()}%"
        q = q.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if country:
        q = q.filter(User.country.ilike(f"%{country.strip()}%"))
    if governorate:
        q = q.filter(User.governorate.ilike(f"%{governorate.strip()}%"))
    if status == "active":
        q = q.filter(User.is_active == True)  # noqa: E712
    elif status == "inactive":
        q = q.filter(User.is_active == False)  # noqa: E712
    if expiring_days is not None:
        now = datetime.utcnow()
        q = q.filter(User.end_at != None, User.end_at >= now, User.end_at <= now + timedelta(days=expiring_days))  # noqa: E711

    users = q.order_by(User.created_at.desc()).limit(limit).all()

    # آخر باقة مؤكّدة لكل عضو (نفس منطق /admin/users) — لعرض/فلترة الباقة
    paid_map: Dict[int, Optional[str]] = {}
    user_ids = [u.id for u in users]
    if user_ids:
        pay_rows = (
            db.query(Payment.user_id, Payment.plan_key, Payment.confirmed_at, Payment.created_at)
            .filter(Payment.user_id.in_(user_ids), Payment.status == PaymentStatus.CONFIRMED)
            .all()
        )
        best_ts: Dict[int, datetime] = {}
        for uid, plan_key, confirmed_at, created_at in pay_rows:
            ts = confirmed_at or created_at or datetime.min
            if uid not in best_ts or ts >= best_ts[uid]:
                best_ts[uid] = ts
                paid_map[uid] = plan_key

    recipients = []
    for u in users:
        pk = paid_map.get(u.id)
        # فلتر الباقة (في Python بعد ما عرفنا آخر باقة مؤكّدة)
        if plan and plan != "all":
            grp = _plan_group(pk)
            if plan == "none":
                if u.id in paid_map:
                    continue
            elif grp != plan:
                continue
        recipients.append(_serialize_recipient(u, pk))

    resp: Dict[str, Any] = {
        "recipients": recipients,
        "returned": len(recipients),
        "truncated": len(users) >= limit,
    }

    if include_facets:
        countries = [c[0] for c in db.query(User.country).filter(User.country != None, User.country != "").distinct().all()]  # noqa: E711
        govs = [g[0] for g in db.query(User.governorate).filter(User.governorate != None, User.governorate != "").distinct().all()]  # noqa: E711
        resp["countries"] = sorted({c for c in countries if c})
        resp["governorates"] = sorted({g for g in govs if g})

    return resp


# ══════════════════════════════════════════════════════════════
#  POST /preview — بناء الـ HTML النهائي لإيميل واحد (معاينة)
# ══════════════════════════════════════════════════════════════

@router.post("/preview")
def preview_email(
    body: PreviewRequest,
    current_user: User = Depends(get_current_user),
):
    require_owner(current_user)
    try:
        content = ecs.build_content(body.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطأ في محتوى الإيميل: {e}")

    sample_row = None
    if body.sample:
        s = body.sample
        sample_row = {
            "Name": s.get("name", "") or "أحمد محمد",
            "Governorate": s.get("governorate", "") or "القاهرة",
            "Country": s.get("country", "") or "Egypt",
            "Email": s.get("email", "") or "member@example.com",
            "Governorate_Ar": s.get("governorate_ar", "") or "",
            "Name_Ar": s.get("name_ar", "") or "",
        }

    result = ecs.render_preview(content, sample_row)
    return result


# ══════════════════════════════════════════════════════════════
#  POST /send — إرسال الحملة (test synchronous / real background)
# ══════════════════════════════════════════════════════════════

def _run_real_send(targets, content, campaign_id, test_emails):
    """Worker الخلفية للإرسال الحقيقي — بيستخدم جلسات DB خاصة به عبر المحرك."""
    try:
        ecs.send_campaign(
            targets=targets,
            content=content,
            campaign_name=campaign_id,
            test_mode=False,
            test_emails=test_emails,
        )
    except Exception:
        logger.exception("Real campaign send failed (campaign_id=%s)", campaign_id)
    finally:
        with _send_lock:
            _active_send.update(running=False, campaign_id=None, total=0, started_at=None)


@router.post("/send")
async def send_campaign_endpoint(
    body: SendRequest,
    current_user: User = Depends(get_current_user),
):
    require_owner(current_user)

    mode = (body.mode or "test").strip().lower()
    if mode not in ("test", "real"):
        raise HTTPException(status_code=400, detail=f"mode لازم يكون test أو real، مش {mode!r}")

    try:
        content = ecs.build_content(body.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطأ في محتوى الإيميل: {e}")

    campaign_id = (body.campaign_id or "").strip() or f"adhoc-{datetime.utcnow():%Y%m%d-%H%M%S}"
    targets = ecs.normalize_recipients(body.recipients)
    if len(targets) > MAX_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"عدد المستلمين أكبر من الحد المسموح ({MAX_RECIPIENTS}).")

    test_emails = [e.strip() for e in (body.test_emails or []) if e and e.strip()] or None

    # ── وضع الاختبار (الافتراضي): synchronous، بيروح لـ test_emails بس ──────────────
    if mode == "test":
        try:
            result = await run_in_threadpool(
                ecs.send_campaign,
                targets=targets,
                content=content,
                campaign_name=campaign_id,
                test_mode=True,
                test_emails=test_emails,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"فشل إرسال التست: {e}")
        return {
            "ok": True,
            "mode": "test",
            "success_count": result.success_count,
            "fail_count": result.fail_count,
            "failures": result.failures,
            "test_emails_used": test_emails or ecs.DEFAULT_TEST_EMAILS,
        }

    # ── الإرسال الحقيقي: محتاج الجملة السرية + بيتنفّذ في الخلفية ──────────────────
    if body.confirm_phrase != CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"❌ الإرسال الحقيقي محتاج confirm_phrase يساوي {CONFIRM_PHRASE} بالظبط.",
        )
    if not targets:
        raise HTTPException(status_code=400, detail="مفيش أي مستلمين في وضع الإرسال الحقيقي.")

    # كام واحد فاضل فعلاً (بعد استبعاد اللي اتبعتلهم قبل كده في نفس الحملة)
    already = ecs.load_sent_log(campaign_id)
    queued = sum(1 for t in targets if t.get("Email") and t["Email"].lower() not in already)
    if queued == 0:
        return {
            "ok": True,
            "mode": "real",
            "started": False,
            "queued": 0,
            "message": "كل المستلمين دول اتبعتلهم قبل كده في نفس الحملة (مفيش تكرار).",
        }

    with _send_lock:
        if _active_send["running"]:
            raise HTTPException(
                status_code=409,
                detail=f"فيه حملة بتتبعت دلوقتي ({_active_send['campaign_id']}). استنى لحد ما تخلص.",
            )
        _active_send.update(running=True, campaign_id=campaign_id, total=queued, started_at=datetime.utcnow().isoformat())

    threading.Thread(
        target=_run_real_send,
        args=(targets, content, campaign_id, test_emails),
        name=f"email-campaign-{campaign_id}",
        daemon=True,
    ).start()

    return {
        "ok": True,
        "mode": "real",
        "started": True,
        "queued": queued,
        "campaign_id": campaign_id,
        "message": f"🚀 بدأ الإرسال الحقيقي لـ {queued} عضو في الخلفية. النتائج بتتسجّل — تابع التقدّم من الحالة.",
    }


# ══════════════════════════════════════════════════════════════
#  GET /status — تقدّم آخر/حملة معيّنة (للـ UI يـ poll بعد بدء إرسال حقيقي)
# ══════════════════════════════════════════════════════════════

@router.get("/status")
def campaign_status(
    campaign_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    sent = (
        db.query(func.count(EmailCampaignSend.id))
        .filter(EmailCampaignSend.campaign_id == campaign_id, EmailCampaignSend.status == "sent")
        .scalar()
    ) or 0
    failed = (
        db.query(func.count(EmailCampaignSend.id))
        .filter(EmailCampaignSend.campaign_id == campaign_id, EmailCampaignSend.status.like("failed%"))
        .scalar()
    ) or 0

    with _send_lock:
        running = bool(_active_send["running"] and _active_send["campaign_id"] == campaign_id)
        queued_total = _active_send["total"] if running else None

    return {
        "campaign_id": campaign_id,
        "sent": sent,
        "failed": failed,
        "processed": sent + failed,
        "running": running,
        "queued_total": queued_total,
    }
