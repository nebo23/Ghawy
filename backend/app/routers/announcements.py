# -*- coding: utf-8 -*-
"""
Community Announcements — حملات جوّه المنصة، مش إيميل.

تاب الإيميلات بيوصل للناس في بريدهم. الحاجة دي بتوصلهم وهُمّ **على الموقع**:
رسالة واحدة بتروح لشريحة من الأعضاء وبتظهر في جرس الإشعارات بتاعهم.

ليه مفيش جدول تسليم لوحده:
    الإرسال بيتحوّل لصفوف `Notification` عادية شايلة `announcement_id`. يعني
    الجرس اللي موجود أصلاً في كل صفحة، وعدّاد غير المقروء، والترجمة، والبولينج
    كل ده بيشتغل من غير أي كود جديد ناحية العضو. وكمان الإحصائيات بتيجي ببلاش:
    «اتسلّمت» = عدد الصفوف بالـ id ده، و«اتقرت» = نفس العدد مفلتر على is_read.

قواعد الأمان — نفس قواعد حملات الإيميل حرف بحرف، والسبب واحد:
  • الافتراضي دايماً تست. التست بيروح **للمرسِل نفسه بس**، مش لأي عضو.
  • الإرسال الحقيقي لازم confirm_phrase == "GHAWY-OFFICIAL-SEND" بالظبط، وإلا 400.
  • إرسالة حقيقية واحدة في نفس اللحظة (قفل) — عشان دبل-كليك ما يبعتش مرتين.
  • الحملة اللي اتبعتت مرة مابتتبعتش تاني. عايز تكررها؟ اعمل نسخة (duplicate).
  • الجمهور بيتحدّد على السيرفر من الفلتر. الفرونت مابيبعتش IDs أبداً — لو بعتها
    يبقى أي حد معاه صلاحية الحملات يقدر يلزق أي id ويوصل لأي حد.
"""
import re
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, cast, func as sql_func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Announcement, Notification, User
from app.routers.users import get_current_user
from app.services import audience as aud
from app.services.permissions import require_permission
from app.services.ws_manager import manager

logger = logging.getLogger("ghawy.announcements")

router = APIRouter(prefix="/admin/announcements", tags=["Announcements"])

CONFIRM_PHRASE = "GHAWY-OFFICIAL-SEND"
ALLOWED_TYPES = {"info", "success", "warning", "promo"}
PREVIEW_SAMPLE = 8

# قفل: إرسالة حقيقية واحدة بس في نفس الوقت.
_send_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════════════

class AnnouncementSave(BaseModel):
    title: str = Field(default="", max_length=160)
    body: str = ""
    type: str = "info"
    link: Optional[str] = None
    audience: Optional[Dict[str, Any]] = None


class SendRequest(BaseModel):
    mode: str = "test"                       # test | real
    confirm_phrase: Optional[str] = None


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def _clean_link(raw: Optional[str]) -> Optional[str]:
    """لينك داخلي بس.

    اللينك ده بيتحقن في `<a href>` في جرس كل عضو. لينك خارجي من تاب الأدمن
    يبقى طريق جاهز لتصيّد الأعضاء باسم المنصة، و`javascript:` يبقى XSS —
    فالمسموح هو مسار داخلي نسبي وبس.
    """
    link = (raw or "").strip()
    if not link:
        return None

    # ── ١) طبّع الأول، وبعدين احكم ─────────────────────────────
    # القاعدة هنا: منقارنش النص اللي المستخدم كتبه — نقارن النص اللي **المتصفح
    # هيشوفه** بعد ما يعمل التطبيع بتاعه. أي فحص بيشتغل على الأصل بيبقى
    # بيحكم على حاجة والمتصفح بينفّذ حاجة تانية.
    #
    #   • control chars: المتصفح بيشيل tab/CR/LF قبل ما يقرا الـ scheme،
    #     فـ "java\tscript:" بيتنفّذ javascript:.
    #   • backslash: في موضع الـ authority المتصفح بيعتبر "\" زي "/"، فـ
    #     "\/evil.com" و "/\evil.com" و "\\evil.com" كلهم بيطلعوا برة الأصل
    #     زي "//evil.com" بالظبط.
    #
    # قايمة سوداء بالإملاءات ("//" و "/\" و "\\" …) بتفضل ناقصة إملاء —
    # النسخة اللي قبل دي كانت بتمسك "/\evil.com" وتفوّت "\/evil.com". التطبيع
    # بيخلّي كل الإملاءات دي شكل واحد، فالفحص بيبقى فحص واحد.
    link = "".join(ch for ch in link if 0x20 <= ord(ch) != 0x7F)
    link = link.replace("\\", "/").strip()
    if not link:
        return None

    lowered = link.lower()

    # ── ٢) أي scheme خالص مرفوض ────────────────────────────────
    # الـ scheme ماينفعش يحتوي على "/" ولا "?" ولا "#"، فاللي قبل أول واحد
    # فيهم هو المكان الوحيد اللي ممكن يبقى فيه scheme. رفض أي ":" هناك بيمسك
    # javascript: و data: و vbscript: و أي حاجة تانية مش مكتوبة في أي قايمة —
    # ومابيرفضش "/x?t=12:30" لأن النقطتين دول بعد "?".
    head = re.split(r"[/?#]", lowered, maxsplit=1)[0]
    if ":" in head:
        raise HTTPException(status_code=400, detail="اللينك لازم يكون مسار داخلي في المنصة")

    # ── ٣) protocol-relative بأي إملاء ─────────────────────────
    # بعد التطبيع فوق، كل إملاءات "//" بقت "//" فعلاً.
    if lowered.startswith("//"):
        raise HTTPException(status_code=400, detail="اللينك لازم يكون مسار داخلي في المنصة")

    # بنرجّع النص المطبّع مش الأصل: اللي اتخزّن لازم يكون بالظبط اللي اتفحص.
    return link[:500]


def _clean_type(raw: Optional[str]) -> str:
    value = (raw or "info").strip().lower()
    return value if value in ALLOWED_TYPES else "info"


def _stats_for(db: Session, ids: List[int]) -> Dict[int, Dict[str, int]]:
    """اتسلّمت/اتقرت لكل حملة — كويري واحدة مجمّعة، مش وحدة لكل حملة."""
    if not ids:
        return {}
    rows = (
        db.query(
            Notification.announcement_id,
            sql_func.count(Notification.id),
            sql_func.sum(cast(Notification.is_read, Integer)),
        )
        .filter(Notification.announcement_id.in_(ids))
        .group_by(Notification.announcement_id)
        .all()
    )
    return {aid: {"delivered": int(total or 0), "read": int(read or 0)} for aid, total, read in rows}


def _serialize(a: Announcement, stats: Optional[Dict[str, int]] = None,
               author_name: Optional[str] = None) -> Dict[str, Any]:
    stats = stats or {"delivered": 0, "read": 0}
    delivered = stats.get("delivered", 0)
    read = stats.get("read", 0)
    return {
        "id": a.id,
        "title": a.title,
        "body": a.body,
        "type": a.type,
        "link": a.link,
        "status": a.status,
        "audience": aud.load_filters(a.audience),
        "created_by": a.created_by,
        "author_name": author_name,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "sent_at": a.sent_at,
        "recipients_count": a.recipients_count or 0,
        "delivered": delivered,
        "read": read,
        "read_rate": round(read * 100 / delivered) if delivered else 0,
    }


def _get_or_404(db: Session, announcement_id: int) -> Announcement:
    row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="الحملة مش موجودة")
    return row


def _require_sendable(a: Announcement) -> None:
    if not (a.title or "").strip() or not (a.body or "").strip():
        raise HTTPException(status_code=400, detail="الحملة محتاجة عنوان ونص قبل الإرسال")


async def _push_live(user_ids: List[int], notif_rows: List[Notification]) -> int:
    """ابعت للأعضاء المتصلين دلوقتي عشان يشوفوها من غير ما يستنوا البولينج.

    بيتبعت للمتصلين بس — الباقي هيشوفها من الجرس خلال ٣٠ ثانية زي أي إشعار
    تاني. أي فشل هنا مايأثرش على الإرسال: الصفوف اتحفظت خلاص، ودي طبقة سرعة
    مش طبقة تسليم.
    """
    pushed = 0
    by_user = {n.user_id: n for n in notif_rows}
    for uid in user_ids:
        if not manager.is_online(uid):
            continue
        n = by_user.get(uid)
        if not n:
            continue
        try:
            await manager.send_personal(uid, {
                "event": "notification",
                "data": {
                    "id": n.id, "title": n.title, "body": n.body,
                    "type": n.type, "link": n.link, "is_read": False,
                },
            })
            pushed += 1
        except Exception:
            logger.debug("live push فشل لليوزر %s — الإشعار متسجّل برضه", uid)
    return pushed


# ══════════════════════════════════════════════════════════════
#  Audience
# ══════════════════════════════════════════════════════════════

@router.get("/audience/preview")
def preview_audience(
    search: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    governorate: Optional[str] = Query(None),
    status: str = Query("all"),
    plan: str = Query("all"),
    expiring_days: Optional[int] = Query(None, ge=0, le=365),
    include_staff: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """كام عضو الفلتر ده بيوصل لهم، ومين هُمّ (عيّنة).

    عيّنة مش القائمة كلها: الشاشة محتاجة رقم وتطمين إن الفلتر ماسك الناس
    الصح، ونقل ٢٠ ألف صف عشان نعرض عدد هو إهدار من غير فايدة.
    """
    require_permission(current_user, "announcements")

    filters = {
        "search": search, "country": country, "governorate": governorate,
        "status": status, "plan": plan, "expiring_days": expiring_days,
        "include_staff": include_staff,
    }
    users = aud.resolve_users(db, filters)
    online = sum(1 for u in users if manager.is_online(u.id))

    return {
        "count": len(users),
        "online_now": online,
        "truncated": len(users) >= aud.MAX_AUDIENCE,
        "sample": [
            {"id": u.id, "full_name": u.full_name, "is_active": bool(u.is_active)}
            for u in users[:PREVIEW_SAMPLE]
        ],
        **aud.facets(db),
    }


# ══════════════════════════════════════════════════════════════
#  CRUD
# ══════════════════════════════════════════════════════════════

@router.get("")
def list_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")

    rows = db.query(Announcement).order_by(Announcement.created_at.desc()).limit(200).all()
    stats = _stats_for(db, [r.id for r in rows])

    author_ids = {r.created_by for r in rows if r.created_by}
    names = {}
    if author_ids:
        names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(author_ids)).all()}

    return [_serialize(r, stats.get(r.id), names.get(r.created_by)) for r in rows]


@router.get("/{announcement_id}")
def get_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    stats = _stats_for(db, [row.id])
    return _serialize(row, stats.get(row.id))


@router.post("", status_code=201)
def create_announcement(
    data: AnnouncementSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """إنشاء مسودة. **مابيبعتش حاجة** — الإرسال ليه إندبوينت لوحده."""
    require_permission(current_user, "announcements")

    row = Announcement(
        title=(data.title or "").strip()[:160],
        body=(data.body or "").strip(),
        type=_clean_type(data.type),
        link=_clean_link(data.link),
        audience=aud.dump_filters(data.audience),
        status="draft",
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("📢 مسودة حملة #%s اتعملت بواسطة user_id=%s", row.id, current_user.id)
    return _serialize(row)


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: int,
    data: AnnouncementSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)

    # حملة اتبعتت = سجل تاريخي. تعديل نصها بعد ما وصل للناس بيخلي اللوحة
    # بتقول حاجة والأعضاء شايفين حاجة تانية.
    if row.status == "sent":
        raise HTTPException(status_code=400, detail="الحملة دي اتبعتت خلاص — اعمل نسخة لو عايز تعدّل")

    row.title = (data.title or "").strip()[:160]
    row.body = (data.body or "").strip()
    row.type = _clean_type(data.type)
    row.link = _clean_link(data.link)
    row.audience = aud.dump_filters(data.audience)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{announcement_id}/duplicate", status_code=201)
def duplicate_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """نسخة جديدة كمسودة — الطريق الوحيد لإعادة إرسال حملة اتبعتت."""
    require_permission(current_user, "announcements")
    src = _get_or_404(db, announcement_id)

    row = Announcement(
        title=f"{src.title} (نسخة)"[:160],
        body=src.body,
        type=src.type,
        link=src.link,
        audience=src.audience,
        status="draft",
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """مسح المسودة. الإشعارات اللي وصلت للأعضاء **مابتتمسحش** —
    `announcement_id` بيتظبط SET NULL، فاللي وصلهم إشعار بيفضل شايفه."""
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    db.delete(row)
    db.commit()
    logger.info("🗑️ حملة #%s اتمسحت بواسطة user_id=%s", announcement_id, current_user.id)


# ══════════════════════════════════════════════════════════════
#  Send
# ══════════════════════════════════════════════════════════════

@router.post("/{announcement_id}/send")
async def send_announcement(
    announcement_id: int,
    payload: SendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    _require_sendable(row)

    # ── تست: للمرسِل هو بس ──
    if payload.mode != "real":
        notif = Notification(
            user_id=current_user.id,
            title=row.title, body=row.body, type=row.type, link=row.link,
            announcement_id=row.id, is_read=False,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        await _push_live([current_user.id], [notif])
        return {"mode": "test", "delivered": 1,
                "message": "الحملة اتبعتت ليك إنت بس — شوفها في الجرس"}

    # ── حقيقي ──
    if (payload.confirm_phrase or "").strip() != CONFIRM_PHRASE:
        raise HTTPException(status_code=400, detail=f'الإرسال الحقيقي محتاج تكتب "{CONFIRM_PHRASE}" بالظبط')

    if row.status == "sent":
        raise HTTPException(status_code=400, detail="الحملة دي اتبعتت خلاص — اعمل نسخة لو عايز تبعتها تاني")

    if not _send_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="في حملة بتتبعت دلوقتي — استنى لما تخلص")

    try:
        filters = aud.load_filters(row.audience)
        users = aud.resolve_users(db, filters)
        if not users:
            raise HTTPException(status_code=400, detail="الفلتر ده مالوش أي عضو — عدّله وجرّب تاني")

        row.status = "sending"
        db.commit()

        # صفوف الإشعارات دفعة واحدة. بنعملها add_all عشان نرجّع الـ ids
        # ونقدر نعمل live push — bulk_insert_mappings أسرع بس مابيرجّعش ids.
        notifs = [
            Notification(
                user_id=u.id, title=row.title, body=row.body,
                type=row.type, link=row.link,
                announcement_id=row.id, is_read=False,
            )
            for u in users
        ]
        db.add_all(notifs)

        row.status = "sent"
        row.sent_at = datetime.utcnow()
        row.recipients_count = len(users)
        db.commit()

        pushed = await _push_live([u.id for u in users], notifs)
        logger.info("📢 حملة #%s اتبعتت لـ %s عضو (%s متصل دلوقتي) بواسطة user_id=%s",
                    row.id, len(users), pushed, current_user.id)

        return {"mode": "real", "delivered": len(users), "pushed_live": pushed,
                "message": f"اتبعتت لـ {len(users)} عضو"}

    except HTTPException:
        db.rollback()
        row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
        if row and row.status == "sending":
            row.status = "draft"
            db.commit()
        raise
    except Exception:
        db.rollback()
        logger.exception("📢 حملة #%s فشلت", announcement_id)
        row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
        if row:
            row.status = "failed"
            db.commit()
        raise HTTPException(status_code=500, detail="الإرسال فشل — الحملة اترجّعت لحالة failed")
    finally:
        _send_lock.release()
