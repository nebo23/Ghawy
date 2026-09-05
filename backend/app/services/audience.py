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

الفلترة كلها بتتنفّذ على السيرفر: الفرونت بيبعت الفلتر، والسيرفر هو اللي بيحدد
مين دول.

الاستثناء الوحيد هو `member_ids` — الاختيار اليدوي بالاسم. وده مضاف عن قصد
وبالشروط دي:

    اللي معاه صلاحية الحملات يقدر أصلاً يوصل لأي عضو لوحده من فلتر `search`
    (بحث بالإيميل الكامل بيرجّع شخص واحد بالظبط)، فالاختيار اليدوي مش قدرة
    جديدة — هو واجهة أحسن لقدرة موجودة. اللي لازم يفضل صح:

      • الـ ids بتتحقق من الداتابيز وقت الحل، مش بتتصدّق زي ما جاية.
      • ليها سقف (MAX_PICKED) — الاختيار اليدوي بالآلاف يبقى فلتر مش اختيار.
      • لما يبقى في اختيار يدوي، باقي الفلاتر بتتلغى. مفيش خلط بيوسّع الجمهور
        من ورا اللي بيبعت.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models import Course, Lesson, Payment, PaymentStatus, User, UserProgress
from app.services.progress_service import effective_lesson_totals

logger = logging.getLogger("ghawy.audience")

# سقف حماية: أكبر جمهور مسموح بيه في إرسالة واحدة.
MAX_AUDIENCE = 20000

# الفلاتر المعروفة. أي مفتاح تاني بيتشال — عشان فلتر متكتب غلط ما يعديش
# صامت ويوسّع الجمهور من غير ما حد ياخد باله.
ALLOWED_KEYS = {
    "search", "country", "governorate", "status", "plan",
    "expiring_days", "include_staff", "member_ids",
    "progress_course_id", "progress_min_percent",
}

# سقف الاختيار اليدوي. الاختيار اليدوي معناه إن حد قعد يدوّر على الناس دول
# بإيده — لو العدد بقى بالآلاف يبقى ده فلتر مش اختيار، والفلاتر ليها مكانها.
MAX_PICKED = 500

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

    # اختيار يدوي لأعضاء بالاسم. بيتخزّن كأرقام نضيفة بس؛ التحقق إن الأرقام
    # دي أعضاء موجودين فعلاً بيحصل وقت الحل (resolve) من الداتابيز نفسها.
    picked = out.get("member_ids")
    if picked in ("", None, []):
        out["member_ids"] = None
    else:
        if not isinstance(picked, (list, tuple, set)):
            picked = [picked]
        clean, seen = [], set()
        for v in picked:
            try:
                uid = int(v)
            except (TypeError, ValueError):
                continue
            if uid > 0 and uid not in seen:
                seen.add(uid)
                clean.append(uid)
            if len(clean) >= MAX_PICKED:
                break
        out["member_ids"] = clean or None

    days = out.get("expiring_days")
    if days in ("", None):
        out["expiring_days"] = None
    else:
        try:
            out["expiring_days"] = max(0, min(365, int(days)))
        except (TypeError, ValueError):
            out["expiring_days"] = None

    # فلتر التقدّم: كورس (أو "أي كورس") + أقل نسبة. مفيش مفتاح تالت لـ"خلّص":
    # ١٠٠٪ هي "خلّص"، وبوليان جنبها كان هيبقى نفس المعنى مكتوب مرتين — واتنين
    # يقدروا يتناقضوا.
    pct = out.get("progress_min_percent")
    if pct in ("", None):
        out["progress_min_percent"] = None
    else:
        try:
            out["progress_min_percent"] = max(0, min(100, int(pct)))
        except (TypeError, ValueError):
            out["progress_min_percent"] = None

    course = out.get("progress_course_id")
    if course in ("", None, 0, "0"):
        out["progress_course_id"] = None            # أي كورس
    else:
        try:
            out["progress_course_id"] = int(course)
        except (TypeError, ValueError):
            out["progress_course_id"] = None

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


# ══════════════════════════════════════════════════════════════
#  فلتر التقدّم — "خلّص الكورس" و"وصل ٨٠٪"
# ══════════════════════════════════════════════════════════════
#
# مش من `user_course_progress.percent`. العمود ده اسمه بيقول إنه الإجابة وهو
# فاضي: مفيش حاجة في المشروع كتبت فيه صف ولا مرة (اتأكد بـ grep)، فالفلتر اللي
# يتبني عليه بيرجّع صفر عضو، بالسكوت، للأبد.
#
# المصدر الحقيقي هو `user_progress` — صف لكل (عضو، درس) خلصه — مقسوم على مقام
# `progress_service.effective_lesson_totals`، اللي هو التعريف الوحيد لعدد
# الدروس اللي بتتحسب في الكورس.


def _min_lessons_for(db: Session, course_ids: List[int], pct: int):
    """أقل عدد دروس يخلّي النسبة اللي العضو شايفها توصل `pct`، لكل كورس.

    النسبة اللي العضو بيقراها في صفحته هي `round(done * 100 / total)`
    (`courses.get_all_progress`)، والمقام هو `effective_lesson_totals`. بنقلب
    نفس المعادلة هنا لعدد دروس بدل ما نكتب حساب نسبة تاني: نسختين لنفس الرقم
    هي بالظبط السبب اللي خلّى نسبة الطالب في صفحته تختلف عن نسبته في لوحة
    الفريق قبل كده، والدوكسترنج بتاعة `effective_lesson_totals` مكتوبة عشان ده.

    وكمان بيخلّي الفلتر مقارنة أرقام صحيحة في الـ SQL — مفيش قسمة ولا تقريب
    جوّه الكويري يقدر يختلف عن تقريب بايثون عند النص في المية.

    بيرجّع `(needs, ready_counts)`: `needs` هي المطلوب لكل كورس، و`ready_counts`
    بتقول أي كورس اتحسب مقامه بالدروس الـ ready — عشان البسط يستخدم نفس الفرع.
    """
    totals, ready_counts = effective_lesson_totals(db, course_ids)
    needs = {}
    for cid in course_ids:
        total = totals.get(cid) or 0
        if total <= 0:
            continue        # كورس من غير دروس: نسبته صفر لكل الناس
        needs[cid] = next(d for d in range(total + 1) if round(d * 100 / total) >= pct)
    return needs, ready_counts


def _progress_user_ids(db: Session, f: Dict[str, Any]):
    """كويري فرعية بأرقام الأعضاء اللي وصلوا النسبة — أو None لو مفيش فلتر.

    جوّه الكويري مش بعديها: فلتر الباقة تحت بيتعمل في بايثون بعد `.limit()`،
    فالسقف بيتطبّق على الجمهور غير المفلتر. ده مقبول هناك لأنه محتاج آخر دفعة
    مؤكّدة لكل عضو؛ التقدّم مش محتاج كده، فهو `IN (subquery)` عادي والـ LIMIT
    بيفضل معناه اللي مكتوب.
    """
    pct = f.get("progress_min_percent")
    if not pct:
        return None         # مفيش نسبة، أو ٠٪ — يعني الكل، يعني مفيش فلتر

    cid = f.get("progress_course_id")
    course_ids = [cid] if cid else [c for (c,) in db.query(Course.id).all()]
    needs, ready_counts = _min_lessons_for(db, course_ids, pct)
    if not needs:
        return None

    # الكورس اللي مقامه اتحسب بالـ ready، بسطه كمان بيتحسب بالـ ready. اللي
    # مفيهوش ولا درس ready بيتحسب بكل دروسه في الاتنين. نفس فرع
    # `courses.get_all_progress` بالحرف.
    branches = []
    ready_ids = [c for c in needs if ready_counts.get(c)]
    all_ids = [c for c in needs if not ready_counts.get(c)]
    if ready_ids:
        branches.append(and_(UserProgress.course_id.in_(ready_ids),
                             Lesson.video_status == "ready"))
    if all_ids:
        branches.append(UserProgress.course_id.in_(all_ids))

    done = (
        db.query(UserProgress.user_id.label("uid"),
                 UserProgress.course_id.label("cid"),
                 func.count(UserProgress.id).label("done"))
        .join(Lesson, Lesson.id == UserProgress.lesson_id)
        .filter(or_(*branches))
        .group_by(UserProgress.user_id, UserProgress.course_id)
        .subquery()
    )
    # كورس مش في `needs` بيدّي NULL، و`done >= NULL` مابتطابقش — وده المطلوب.
    return (
        db.query(done.c.uid)
        .filter(done.c.done >= case(needs, value=done.c.cid, else_=None))
        .scalar_subquery()
    )


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

    # ── اختيار يدوي: الأعضاء دول بالظبط ─────────────────────────
    # لما يكون في اختيار يدوي، هو الجمهور. باقي الفلاتر بتتلغى عن قصد: خلط
    # «الخمس ناس دول» مع «وكمان كل النشطين في مصر» مالوش معنى واضح، والعدّاد
    # في الشاشة كان هيقول رقم غير اللي هيتبعت.
    #
    # الـ ids بتتحقق من الداتابيز هنا — مش بتتصدّق زي ما جاية. اللي مش موجود
    # بيتشال بهدوء بدل ما يكسر الإرسالة كلها.
    if f.get("member_ids"):
        return (
            db.query(User)
            .filter(User.id.in_(f["member_ids"][:limit]))
            .order_by(User.full_name.asc())
            .all()
        )

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

    progress = _progress_user_ids(db, f)
    if progress is not None:
        q = q.filter(User.id.in_(progress))

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


def facets(db: Session) -> Dict[str, Any]:
    """قوائم البلاد والمحافظات والكورسات الموجودة فعلاً — عشان الفلاتر في الواجهة."""
    countries = [c[0] for c in db.query(User.country)
                 .filter(User.country != None, User.country != "").distinct().all()]  # noqa: E711
    govs = [g[0] for g in db.query(User.governorate)
            .filter(User.governorate != None, User.governorate != "").distinct().all()]  # noqa: E711
    return {
        "countries": sorted({c for c in countries if c}),
        "governorates": sorted({g for g in govs if g}),
        # كل الكورسات مش المنشورة بس: عضو ممكن يكون خلّص كورس اتشال من النشر
        # بعدها، وتقدّمه ده حقيقي وبيتحسب.
        "courses": [{"id": c.id, "title": c.title}
                    for c in db.query(Course).order_by(Course.sort_order, Course.id).all()],
    }
