# -*- coding: utf-8 -*-
"""
audience.py — من هم الأعضاء اللي الحملة دي بتروح ليهم.

الفلاتر هنا هي نفس فلاتر تاب الإيميلات بالظبط (الحالة، الباقة، البلد، المحافظة،
الاشتراكات اللي قربت تخلص، البحث بالاسم/الإيميل) — عشان الاتنين يوصلوا لنفس
الجمهور بنفس المعنى، ولما حد يقول "الأعضاء النشطين" يبقى قاصد نفس الناس في
الشاشتين.

ليه ملف لوحده وليه ما اتغيّرش email_campaigns.py:
    `get_recipients` في email_campaigns.py بيعمل نفس الفلترة، بس بيرجّع صفوف
    مجهّزة للإيميل (اسم عربي، محافظة معرّبة، جودة الداتا). اللي محتاجينه هنا هو
    اليوزرز نفسهم. الفلترة اتنقلت هنا بحيث الحملات الجوّه-تطبيق تستخدمها
    مباشرةً، و email_campaigns يقدر ياخدها بعدين من غير ما يتغيّر سلوكه
    النهاردة — ده مسار إرسال إيميلات شغّال في الإنتاج ومش جزء من التغيير ده.

الفلترة كلها بتتنفّذ على السيرفر: الفرونت بيبعت الفلتر، مش قائمة IDs. لو بعت
IDs يبقى أي حد معاه صلاحية الحملات يقدر يلزق أي id ويوصل لأي حد.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Payment, PaymentStatus, User

logger = logging.getLogger("ghawy.audience")

# سقف حماية: أكبر جمهور مسموح بيه في إرسالة واحدة.
MAX_AUDIENCE = 20000

# الفلاتر المعروفة. أي مفتاح تاني بيتشال — عشان فلتر متكتب غلط ما يعديش
# صامت ويوسّع الجمهور من غير ما حد ياخد باله.
ALLOWED_KEYS = {
    "search", "country", "governorate", "status", "plan",
    "expiring_days", "include_staff",
}

_PLAN_GROUPS = {
    "monthly": {"monthly", "month", "1m"},
    "quarterly": {"quarterly", "quarter", "3m"},
    "yearly": {"yearly", "year", "annual", "12m"},
}


def normalize_filters(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """رجّع فلتر نظيف فيه المفاتيح المعروفة بس، بقيم مضبوطة."""
    raw = raw or {}
    out: Dict[str, Any] = {k: v for k, v in raw.items() if k in ALLOWED_KEYS}

    out["status"] = out.get("status") or "all"
    out["plan"] = out.get("plan") or "all"
    out["include_staff"] = bool(out.get("include_staff"))

    for key in ("search", "country", "governorate"):
        val = (out.get(key) or "").strip()
        out[key] = val or None

    days = out.get("expiring_days")
    if days in ("", None):
        out["expiring_days"] = None
    else:
        try:
            out["expiring_days"] = max(0, min(365, int(days)))
        except (TypeError, ValueError):
            out["expiring_days"] = None

    return out


def dump_filters(filters: Optional[Dict[str, Any]]) -> str:
    return json.dumps(normalize_filters(filters), ensure_ascii=False)


def load_filters(raw: Optional[str]) -> Dict[str, Any]:
    """اقرا الفلتر المتخزّن. فلتر تالف = فلتر فاضي، مش الجمهور كله."""
    if not raw:
        return normalize_filters({})
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("audience filter غير صالح — بنقع على الفلتر الفاضي")
        return normalize_filters({})
    return normalize_filters(parsed if isinstance(parsed, dict) else {})


def latest_plan_map(db: Session, user_ids: List[int]) -> Dict[int, Optional[str]]:
    """آخر باقة مؤكّدة لكل عضو — نفس منطق /admin/users و/recipients."""
    if not user_ids:
        return {}
    rows = (
        db.query(Payment.user_id, Payment.plan_key, Payment.confirmed_at, Payment.created_at)
        .filter(Payment.user_id.in_(user_ids), Payment.status == PaymentStatus.CONFIRMED)
        .all()
    )
    best_ts: Dict[int, datetime] = {}
    plans: Dict[int, Optional[str]] = {}
    for uid, plan_key, confirmed_at, created_at in rows:
        ts = confirmed_at or created_at or datetime.min
        if uid not in best_ts or ts >= best_ts[uid]:
            best_ts[uid] = ts
            plans[uid] = plan_key
    return plans


def plan_group(plan_key: Optional[str]) -> str:
    key = (plan_key or "").strip().lower()
    for group, names in _PLAN_GROUPS.items():
        if key in names:
            return group
    return "none" if not key else "other"


def resolve_users(db: Session, filters: Optional[Dict[str, Any]],
                  limit: int = MAX_AUDIENCE) -> List[User]:
    """الأعضاء اللي مطابقين الفلتر ده، دلوقتي.

    بتتنده وقت الإرسال مش وقت الحفظ — جمهور زي "اشتراكه بيخلص خلال 7 أيام"
    معناه ناس مختلفين كل يوم، وده المقصود منه.
    """
    f = normalize_filters(filters)
    q = db.query(User)

    # الستاف مستبعدين افتراضياً: الحملة موجّهة للأعضاء، ومحدش عايز يبعت لنفسه
    # إعلان "جدّد اشتراكك".
    if not f["include_staff"]:
        q = q.filter(User.is_admin == False, User.is_owner == False)  # noqa: E712

    if f["search"]:
        term = f"%{f['search']}%"
        q = q.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if f["country"]:
        q = q.filter(User.country.ilike(f"%{f['country']}%"))
    if f["governorate"]:
        q = q.filter(User.governorate.ilike(f"%{f['governorate']}%"))

    if f["status"] == "active":
        q = q.filter(User.is_active == True)  # noqa: E712
    elif f["status"] == "inactive":
        q = q.filter(User.is_active == False)  # noqa: E712

    if f["expiring_days"] is not None:
        now = datetime.utcnow()
        q = q.filter(
            User.end_at != None,  # noqa: E711
            User.end_at >= now,
            User.end_at <= now + timedelta(days=f["expiring_days"]),
        )

    users = q.order_by(User.created_at.desc()).limit(limit).all()

    # فلتر الباقة بيتعمل بعد الكويري لأنه محتاج آخر دفعة مؤكّدة لكل عضو.
    if f["plan"] and f["plan"] != "all":
        plans = latest_plan_map(db, [u.id for u in users])
        wanted = f["plan"]
        if wanted == "none":
            users = [u for u in users if u.id not in plans]
        else:
            users = [u for u in users if plan_group(plans.get(u.id)) == wanted]

    return users


def facets(db: Session) -> Dict[str, List[str]]:
    """قوائم البلاد والمحافظات الموجودة فعلاً — عشان الفلاتر في الواجهة."""
    countries = [c[0] for c in db.query(User.country)
                 .filter(User.country != None, User.country != "").distinct().all()]  # noqa: E711
    govs = [g[0] for g in db.query(User.governorate)
            .filter(User.governorate != None, User.governorate != "").distinct().all()]  # noqa: E711
    return {
        "countries": sorted({c for c in countries if c}),
        "governorates": sorted({g for g in govs if g}),
    }
