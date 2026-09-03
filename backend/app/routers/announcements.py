# -*- coding: utf-8 -*-
"""
Community Announcements — حملات جوّه المنصة، مش إيميل.

تاب الإيميلات بيوصل للناس في بريدهم. الحاجة دي بتوصلهم وهُمّ **على الموقع**،
بواحدة من طريقتين (`delivery`):

  • `"bell"` (الافتراضي) — صف `Notification` بيظهر في جرس الإشعارات.
  • `"dm"` — رسالة خاصة حقيقية من حساب أدمن مختار، بتوصل في الرسايل الخاصة.

ليه مفيش جدول تسليم لوحده:
    الإرسال بيتحوّل لصفوف موجودة أصلاً شايلة `announcement_id` — `Notification`
    في وضع الجرس، و`Message` في وضع الرسالة الخاصة. يعني الجرس اللي موجود في
    كل صفحة، وعدّاد غير المقروء، وقايمة الرسايل، وإيصالات القراءة
    (`MessageRead`) كلها بتشتغل من غير أي كود جديد ناحية العضو. وكمان
    الإحصائيات بتيجي ببلاش: «اتسلّمت» = عدد الصفوف بالـ id ده، و«اتقرت» = نفس
    العدد مفلتر على القراءة.

قواعد الأمان — نفس قواعد حملات الإيميل حرف بحرف، والسبب واحد:
  • الافتراضي دايماً تست. التست بيروح **للمرسِل نفسه بس**، مش لأي عضو.
  • الإرسال الحقيقي لازم confirm_phrase == "GHAWY-OFFICIAL-SEND" بالظبط، وإلا 400.
  • إرسالة حقيقية واحدة في نفس اللحظة (قفل) — عشان دبل-كليك ما يبعتش مرتين.
  • الحملة اللي اتبعتت مرة مابتتبعتش تاني. عايز تكررها؟ اعمل نسخة (duplicate).
  • الجمهور بيتحدّد على السيرفر من الفلتر. الفرونت مابيبعتش IDs أبداً — لو بعتها
    يبقى أي حد معاه صلاحية الحملات يقدر يلزق أي id ويوصل لأي حد.

──────────────────────────────────────────────────────────────────────
القرارات اللي القواعد اللي فوق مكانتش بتغطيها، ومتكتبة هنا عشان تفضل مكتوبة:

١) الحملة اللي فشلت بتكمّل، مابتتبعتش من الأول (resume)
    القاعدة "اللي اتبعتت مابتتبعتش تاني" موجودة عشان حاجة واحدة: التسليم
    المكرّر هو الحاجة الوحيدة في الفيتشر دي اللي مفيش رجوع فيها. بس القاعدة
    كانت بتقيس على `status == "sent"` بس، والحملة اللي وقعت في نص الفان-آوت
    بتقف على `failed` ومعاها ناس استلمت فعلاً — فإعادة الإرسال كانت بتوصلهم
    مرتين، وهي بالظبط الحاجة اللي القاعدة اتعملت تمنعها.
    الحل مش منع الإعادة (ده بيسيب الحملة في طريق مسدود)، الحل إن الإعادة
    **تكمّل**: الصفوف شايلة `announcement_id`، يعني مين استلم معروف. فالإرسال
    التاني بيستبعد اللي استلموا خلاص ويبعت للباقي بس.
    والاستبعاد ده بيشتغل في حالة الإكمال بس (`failed` أو `sending` واقفة من
    غير ثريد). إرسالة أول مرة مفيهاش حاجة تتكمّل، ولو طبّقنا الاستبعاد عليها
    كان هيبلع صف التست اللي المرسِل بعته لنفسه بإيده.

٢) الحملة المجدولة اللي فات ميعادها بمدة كبيرة مابتتبعتش
    مفيش حد أقصى للتأخير كان معناه إن ٣ أيام downtime بتخلي «الكورس الجديد نزل
    النهاردة» توصل بعد ٣ أيام لكل الناس. القرار: أي حملة عدّى على ميعادها أكتر
    من `SCHEDULE_GRACE` بتتقفل على `failed` مع سبب مكتوب، وأقل من كده بتتبعت
    عادي (restart أو ديبلوي المفروض ما يضيّعش حملة).
    الـ ٣ ساعات مش رقم عشوائي: أطول توقف اتسجّل على السيرفر ده كان أقل من
    ساعة، وحملة اتأخرت أكتر من ٣ ساعات بتكون فاتت لحظتها فعلاً — إعلان
    بالليل بـ ٣ ساعات تأخير بيوصل بعد نص الليل. الحملة دي عايزة تتكتب من
    تاني، مش تتبعت.

٣) وضع الرسالة الخاصة: مين الرسالة **من** عنده
    فيه حقلين مختلفين عن قصد:
      • `sender_id` — الحساب اللي العضو هيشوف الرسالة جاية منه.
      • `sent_by`   — مين اللي ضغط الزرار فعلاً.
    القواعد (كلها مفروضة على السيرفر، والـ dropdown في الواجهة تسهيل مش فحص):
      • `sender_id` لازم يبقى أدمن أو owner. مستحيل يبقى عضو عادي.
      • الـ owner لوحده هو اللي يقدر يخلي `sender_id` حد غيره. الأدمن اللي
        معاه صلاحية الحملات يبعت باسمه هو وبس — من غير القاعدة دي أي أدمن
        يقدر يحطّ كلام في بُقّ أدمن تاني، والسجل اللي العضو شايفه بيقول إن
        الأدمن ده كتبه.
      • الاتنين بيتخزنوا دايماً حتى لو نفس الشخص: سجل التدقيق لازم يجاوب
        «مين بعت ده فعلاً» بمعزل عن اللي العضو شافه.
    ولما `sender_id != sent_by` صاحب الحساب بياخد إشعار إن حملة خرجت من
    حسابه. مش مجاملة: الراجل ده هيوصله ردود على محادثة هو مابدأهاش، ومعرفته
    بيها من الردود نفسها هي أسرع طريقة تخسر بيها ثقته في الأداة.

٤) الرسالة الخاصة دعوة للرد، والجرس لأ
    إشعار الجرس اتجاه واحد. الرسالة الخاصة بتفتح محادثة. حملة DM على الروستر
    كله بتعمل آلاف المحادثات الحقيقية، كلها بتقع في بريد شخص واحد، ومحدش
    خصّص حد للرد عليها. عشان كده الرقم والجملة دي بيتعرضوا في ديالوج التأكيد
    نفسه — عند نقطة اتخاذ القرار، مش في tooltip جنبها.
"""
import os
import re
import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, and_, cast, func as sql_func, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
    Announcement, AnnouncementSegment, ChatMember, Message, MessageRead,
    MessageType, Notification, User,
)
from app.routers.users import get_current_user
from app.services import audience as aud
from app.services import dm_service
from app.services.permissions import has_permission, require_permission
from app.services.ws_manager import manager

logger = logging.getLogger("ghawy.announcements")

router = APIRouter(prefix="/admin/announcements", tags=["Announcements"])

CONFIRM_PHRASE = "GHAWY-OFFICIAL-SEND"
ALLOWED_TYPES = {"info", "success", "warning", "promo"}
DELIVERY_MODES = {"bell", "dm"}
ALLOWED_STATUSES = {"draft", "scheduled", "sending", "sent", "failed"}
PREVIEW_SAMPLE = 8
LIST_PAGE_DEFAULT = 30
LIST_PAGE_MAX = 100

# الفان-آوت بيتقطّع لدفعات وكل دفعة بتتحفظ لوحدها. الرقم مش عن الأداء بس:
# لو الوركر وقع في النص، اللي اتحفظ بيفضل محفوظ، والإرسال التاني بيكمّل من
# عنده (شوف القرار ١ فوق). لو الترانزاكشن كانت واحدة كبيرة كان الوقوع بيرمي
# كل حاجة ويرجّعنا نقطة الصفر في كل مرة.
SEND_CHUNK = 500

# أقصى تأخير مسموح بيه لحملة مجدولة (القرار ٢ فوق).
SCHEDULE_GRACE = timedelta(hours=3)
STALE_SCHEDULE_REASON = (
    "فات ميعادها بأكتر من 3 ساعات — اتلغت بدل ما تتبعت متأخرة. "
    "لو لسه عايزها، اعمل نسخة واجدولها من تاني."
)

# قفل: إرسالة حقيقية واحدة بس في نفس الوقت. بيتاخد في الريكوست وبيتفك في
# الثريد اللي بيعمل الفان-آوت — الإرسال بيعيش بعد الريكوست دلوقتي.
# gunicorn شغّال بـ workers=1، فالقفل ده فعلاً على مستوى التطبيق كله.
_send_lock = threading.Lock()

# صورة جوّه-البروسيس عن الإرسالة الشغّالة. عمود `status` هو المصدر الباقي بعد
# أي restart؛ ده بيضيف "في ثريد شغّال عليها دلوقتي؟" — واللي بيسمح نفرّق بين
# حملة بتتبعت وحملة الوركر وقع وهو بيبعتها. بيتكتب من ماسك القفل بس.
_active_send: Dict[str, Any] = {
    "running": False, "announcement_id": None, "total": 0, "started_at": None,
}


# ══════════════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════════════

class AnnouncementSave(BaseModel):
    title: str = Field(default="", max_length=160)
    body: str = ""
    type: str = "info"
    link: Optional[str] = None
    audience: Optional[Dict[str, Any]] = None
    delivery: str = "bell"
    # وضع الـ DM بس. `None` معناها "أنا" — بيتحسم على السيرفر، والفحص كامل هناك.
    sender_id: Optional[int] = None


class SendRequest(BaseModel):
    mode: str = "test"                       # test | real
    confirm_phrase: Optional[str] = None


class ScheduleRequest(BaseModel):
    # ISO-8601. The confirm phrase is required HERE and not when the job fires:
    # the decision to send to everybody must be made by a person, and at fire
    # time there is nobody to make it.
    scheduled_for: str
    confirm_phrase: Optional[str] = None


class SegmentSave(BaseModel):
    name: str = Field(default="", max_length=80)
    filters: Optional[Dict[str, Any]] = None


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


def _clean_delivery(raw: Optional[str]) -> str:
    """أي قيمة مش معروفة بتقع على "bell".

    الاتجاه ده مقصود: القيمة الغلط بتوصل إشعار جرس، مش رسالة خاصة لكل الروستر.
    """
    value = (raw or "bell").strip().lower()
    return value if value in DELIVERY_MODES else "bell"


def _chunks(seq: Sequence[int], size: int) -> Iterable[Sequence[int]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _resolve_sender(db: Session, actor: User, delivery: str,
                    requested: Optional[int]) -> Optional[int]:
    """مين الرسالة هتبان جاية منه — بالفحص الكامل (القرار ٣ في الدوكسترينج).

    بتتنده وقت الحفظ **ووقت الإرسال**: الأدمن ممكن تكون اتشالت منه الصلاحية
    أو بقى مش أدمن بين اللحظتين، والحملة المتخزّنة لوحدها مش إثبات على حاجة.
    """
    if delivery != "dm":
        # في وضع الجرس مفيش "من" أصلاً — بس اللي المستخدم اختاره بيتحفظ عشان
        # لو رجّع الحملة DM تاني يلاقي اختياره مكانه.
        return requested if requested else None

    sender_id = int(requested) if requested else int(actor.id)

    if sender_id != int(actor.id) and not getattr(actor, "is_owner", False):
        raise HTTPException(
            status_code=403,
            detail="الأدمن يقدر يبعت باسمه هو بس — الـ owner لوحده اللي يقدر يبعت باسم حد تاني",
        )

    sender = db.query(User).filter(User.id == sender_id).first()
    if not sender:
        raise HTTPException(status_code=400, detail="الحساب المرسِل مش موجود")
    if not (sender.is_admin or sender.is_owner):
        raise HTTPException(
            status_code=400,
            detail="الرسالة الخاصة لازم تتبعت من حساب أدمن — مينفعش حساب عضو عادي",
        )
    return sender_id


def _stats_for(db: Session, rows: Sequence[Announcement]) -> Dict[int, Dict[str, int]]:
    """اتسلّمت/اتقرت لكل حملة — كويري مجمّعة لكل وضع تسليم، مش وحدة لكل حملة.

    اتنين مش واحدة لأن الوضعين بيكتبوا في جدولين مختلفين. والصفحة اللي مفيهاش
    ولا حملة DM بتفضل كويري واحدة بالظبط زي الأول.
    """
    out: Dict[int, Dict[str, int]] = {}
    bell_ids = [r.id for r in rows if (r.delivery or "bell") != "dm"]
    dm_ids = [r.id for r in rows if (r.delivery or "bell") == "dm"]

    if bell_ids:
        for aid, total, read in (
            db.query(
                Notification.announcement_id,
                sql_func.count(Notification.id),
                sql_func.sum(cast(Notification.is_read, Integer)),
            )
            .filter(Notification.announcement_id.in_(bell_ids))
            .group_by(Notification.announcement_id)
            .all()
        ):
            out[aid] = {"delivered": int(total or 0), "read": int(read or 0)}

    if dm_ids:
        # "اتقرت" هنا = الرسالة عليها إيصال قراءة من حد **غير المرسِل**. في
        # المحادثة الخاصة الطرفين اتنين بس، فالتاني ده هو العضو. بنعيد استخدام
        # `MessageRead` اللي الشات بيكتبه أصلاً بدل ما نخترع آلية تانية.
        for aid, total, read in (
            db.query(
                Message.announcement_id,
                sql_func.count(sql_func.distinct(Message.id)),
                sql_func.count(sql_func.distinct(MessageRead.message_id)),
            )
            .outerjoin(
                MessageRead,
                and_(MessageRead.message_id == Message.id,
                     MessageRead.user_id != Message.sender_id),
            )
            .filter(Message.announcement_id.in_(dm_ids))
            .group_by(Message.announcement_id)
            .all()
        ):
            out[aid] = {"delivered": int(total or 0), "read": int(read or 0)}

    return out


def _delivered_count(db: Session, row: Announcement) -> int:
    """كام صف اتكتب فعلاً للحملة دي لحد دلوقتي — مهما كانت حالتها."""
    if (row.delivery or "bell") == "dm":
        return int(db.query(sql_func.count(Message.id))
                   .filter(Message.announcement_id == row.id).scalar() or 0)
    return int(db.query(sql_func.count(Notification.id))
               .filter(Notification.announcement_id == row.id).scalar() or 0)


def _delivered_user_ids(db: Session, row: Announcement) -> set:
    """مين استلم الحملة دي خلاص — الأساس اللي الإكمال بيبني عليه (القرار ١)."""
    if (row.delivery or "bell") == "dm":
        rows = (
            db.query(ChatMember.user_id)
            .join(Message, Message.channel_id == ChatMember.channel_id)
            .filter(Message.announcement_id == row.id,
                    ChatMember.user_id != Message.sender_id)
            .distinct()
            .all()
        )
        return {r[0] for r in rows}
    rows = (
        db.query(Notification.user_id)
        .filter(Notification.announcement_id == row.id)
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _serialize(a: Announcement, stats: Optional[Dict[str, int]] = None,
               author_name: Optional[str] = None,
               sender_name: Optional[str] = None) -> Dict[str, Any]:
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
        "delivery": a.delivery or "bell",
        "sender_id": a.sender_id,
        "sender_name": sender_name,
        "sent_by": a.sent_by,
        "failure_reason": a.failure_reason,
        "audience": aud.load_filters(a.audience),
        "created_by": a.created_by,
        "author_name": author_name,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "sent_at": a.sent_at,
        "scheduled_for": a.scheduled_for,
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


def _dm_body(a: Announcement) -> str:
    """نص الرسالة الخاصة زي ما العضو هيقراه.

    الرسالة الخاصة مالهاش عنوان منفصل زي الجرس، فالعنوان بيتحط أول سطر.
    واللينك بيتكتب كـ URL كامل عشان الشات بيعمل linkify للـ URLs بس (شوف
    `linkifyText` في utils.js) — مسار نسبي كان هيوصل كنص ميّت.
    """
    parts = []
    title = (a.title or "").strip()
    body = (a.body or "").strip()
    if title:
        parts.append(title)
    if body:
        parts.append(body)
    if a.link:
        base = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
        parts.append(f"{base}/{a.link.lstrip('/')}")
    return "\n\n".join(parts)


def _live_item(notif_id: int, user_id: int, a: Announcement) -> Dict[str, Any]:
    """الحمولة اللي بتتبعت على الـ WebSocket — ديكشنري عادي، مش صف ORM.

    مهم إنها dict: الإرسال الحقيقي بيحصل في ثريد، والـ push بيتنفّذ على الـ
    event loop بتاع التطبيق. لو عدّينا صفوف ORM بين الاتنين كنا هنقرا من جلسة
    اتقفلت في ثريد تاني.
    """
    return {
        "user_id": user_id,
        "data": {
            "id": notif_id, "title": a.title, "body": a.body,
            "type": a.type, "link": a.link, "is_read": False,
        },
    }


async def _push_live(items: List[Dict[str, Any]]) -> int:
    """ابعت للأعضاء المتصلين دلوقتي عشان يشوفوها من غير ما يستنوا البولينج.

    بيتبعت للمتصلين بس — الباقي هيشوفها من الجرس خلال ٣٠ ثانية زي أي إشعار
    تاني. أي فشل هنا مايأثرش على الإرسال: الصفوف اتحفظت خلاص، ودي طبقة سرعة
    مش طبقة تسليم.
    """
    pushed = 0
    for item in items:
        uid = item["user_id"]
        if not manager.is_online(uid):
            continue
        try:
            await manager.send_personal(uid, {"event": "notification", "data": item["data"]})
            pushed += 1
        except Exception:
            logger.debug("live push فشل لليوزر %s — الإشعار متسجّل برضه", uid)
    return pushed


async def _push_live_dm(items: List[Dict[str, Any]]) -> int:
    """نفس الفكرة بس للرسايل الخاصة.

    بيتبعت حاجتين لكل رسالة، بالظبط زي ما `POST /chat/messages` بيعمل:
    `new_message` على القناة (صفحة الرسايل بتعيد التحميل عليه) و
    `new_notification` للعضو (عشان الجرس/الشارة).
    """
    pushed = 0
    for item in items:
        uid = item["user_id"]
        if not manager.is_online(uid):
            continue
        try:
            await manager.broadcast_to_channel(item["channel_id"], {
                "event": "new_message", "data": item["message"],
            })
            await manager.send_personal(uid, {
                "event": "new_notification",
                "data": {"title": f"💬 {item['sender_name']}", "body": item["preview"]},
            })
            pushed += 1
        except Exception:
            logger.debug("live DM push فشل لليوزر %s — الرسالة متسجّلة برضه", uid)
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
    member_ids: Optional[List[int]] = Query(None),
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
        "include_staff": include_staff, "member_ids": member_ids,
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
#  Member picker
# ══════════════════════════════════════════════════════════════

@router.get("/members/search")
def search_members(
    q: str = Query("", description="اسم أو إيميل"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """دوّر على أعضاء بالاسم أو الإيميل عشان تختارهم بإيدك.

    الإيميل هنا بيمشي على نفس قاعدة باقي اللوحة بالحرف (شوف
    `GET /admin/users` في admin.py): من غير صلاحية `member-contacts` الإيميل
    مابيترجعش — **والبحث بيه كمان مابيشتغلش**. القاعدة التانية دي هي المهمة:
    لو سيبنا البحث بالإيميل شغّال والعرض مقفول، يبقى الشاشة بقت أداة تخمين
    إيميلات (تكتب إيميل وتشوف لو رجع حد) وهي بالظبط اللي الصلاحية موجودة
    تمنعها.

    بيرجّع عدد صغير: دي قايمة اختيار جنب خانة بحث، مش تصدير للروستر.
    """
    require_permission(current_user, "announcements")
    sees_contacts = has_permission(current_user, "member-contacts")

    term = (q or "").strip()
    if len(term) < 2:
        return {"items": [], "sees_contacts": sees_contacts}

    like = f"%{term}%"
    conditions = [User.full_name.ilike(like)]
    if sees_contacts:
        conditions.append(User.email.ilike(like))

    rows = (
        db.query(User)
        .filter(or_(*conditions))
        .order_by(User.is_active.desc(), User.full_name.asc())
        .limit(limit)
        .all()
    )
    return {
        "sees_contacts": sees_contacts,
        "items": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email if sees_contacts else None,
                "avatar_url": u.avatar_url,
                "is_active": bool(u.is_active),
                "is_staff": bool(u.is_admin or u.is_owner),
            }
            for u in rows
        ],
    }


@router.get("/members/resolve")
def resolve_members(
    ids: Optional[List[int]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """أسامي الأعضاء المختارين، عشان الشاشة تعرض شرايح بأسماء مش أرقام.

    محتاجة لما حملة متحفوظة تتفتح تاني: المتخزّن هو الـ ids، واللي بيفتحها
    لازم يشوف مين دول قبل ما يبعت.
    """
    require_permission(current_user, "announcements")
    sees_contacts = has_permission(current_user, "member-contacts")
    if not ids:
        return {"items": [], "sees_contacts": sees_contacts}

    rows = (
        db.query(User)
        .filter(User.id.in_(ids[:aud.MAX_PICKED]))
        .order_by(User.full_name.asc())
        .all()
    )
    return {
        "sees_contacts": sees_contacts,
        "items": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email if sees_contacts else None,
                "avatar_url": u.avatar_url,
                "is_active": bool(u.is_active),
                "is_staff": bool(u.is_admin or u.is_owner),
            }
            for u in rows
        ],
    }


# ══════════════════════════════════════════════════════════════
#  Saved segments
# ══════════════════════════════════════════════════════════════
#
# المقطع بيخزّن **الفلتر**، مش قائمة أعضاء — نفس سبب الحملة بالظبط: الروستر
# بيتغيّر كل يوم، و«اللي اشتراكه بيخلص الأسبوع ده» لازم تفضل معناها ده.
#
# ومسح المقطع مابيلمسش الحملات اللي اتبنت منه: الحملة بتنسخ الفلتر في عمودها
# هي وقت الحفظ، فالاتنين بيبطلوا يكونوا مربوطين من لحظة النسخ.

def _serialize_segment(s: AnnouncementSegment, author_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "filters": aud.load_filters(s.filters),
        "created_by": s.created_by,
        "author_name": author_name,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


@router.get("/segments")
def list_segments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    rows = db.query(AnnouncementSegment).order_by(AnnouncementSegment.name.asc()).all()
    author_ids = {r.created_by for r in rows if r.created_by}
    names = {}
    if author_ids:
        names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(author_ids)).all()}
    return [_serialize_segment(r, names.get(r.created_by)) for r in rows]


@router.post("/segments", status_code=201)
def create_segment(
    data: SegmentSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    name = (data.name or "").strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="المقطع محتاج اسم")

    row = db.query(AnnouncementSegment).filter(AnnouncementSegment.name == name).first()
    if row:
        # نفس الاسم = تحديث، مش صف تاني. اتنين بنفس الاسم في الـ dropdown
        # مالهومش أي معنى للي بيختار.
        row.filters = aud.dump_filters(data.filters)
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_segment(row)

    row = AnnouncementSegment(
        name=name,
        filters=aud.dump_filters(data.filters),
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("🎯 مقطع جمهور «%s» اتحفظ بواسطة user_id=%s", name, current_user.id)
    return _serialize_segment(row)


@router.delete("/segments/{segment_id}", status_code=204)
def delete_segment(
    segment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """امسح المقطع. الحملات اللي اتعملت منه **مابتتلمسش** — كل واحدة شايلة
    نسخة الفلتر بتاعتها في عمودها هي."""
    require_permission(current_user, "announcements")
    row = db.query(AnnouncementSegment).filter(AnnouncementSegment.id == segment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="المقطع مش موجود")
    db.delete(row)
    db.commit()


# ══════════════════════════════════════════════════════════════
#  Senders (DM mode)
# ══════════════════════════════════════════════════════════════

@router.get("/senders")
def list_senders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """الحسابات اللي الشخص ده مسموح له يبعت باسمها.

    الـ owner بيشوف كل الأدمن والـ owner؛ أي حد تاني بيشوف نفسه وبس. القايمة
    دي تسهيل للواجهة — الفحص الحقيقي في `_resolve_sender` على كل حفظ وكل
    إرسال، فحتى لو حد بعت id مش في القايمة دي بيترفض.
    """
    require_permission(current_user, "announcements")

    if getattr(current_user, "is_owner", False):
        rows = (
            db.query(User)
            .filter(or_(User.is_admin.is_(True), User.is_owner.is_(True)))
            .order_by(User.is_owner.desc(), User.full_name.asc())
            .all()
        )
    else:
        rows = [current_user]

    return [
        {"id": u.id, "full_name": u.full_name, "avatar_url": u.avatar_url,
         "is_owner": bool(u.is_owner), "is_self": u.id == current_user.id}
        for u in rows
    ]


# ══════════════════════════════════════════════════════════════
#  CRUD
# ══════════════════════════════════════════════════════════════

@router.get("")
def list_announcements(
    q: Optional[str] = Query(None, description="بحث في العنوان والنص"),
    status: str = Query("all", description="all | draft | scheduled | sending | sent | failed"),
    delivery: str = Query("all", description="all | bell | dm"),
    limit: int = Query(LIST_PAGE_DEFAULT, ge=1, le=LIST_PAGE_MAX),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """قايمة الحملات — بصفحات، وبفلترة وبحث.

    كانت `.limit(200)` من غير أي حاجة تانية، وده بيكفي لحد ما الحملة رقم ٢٠١
    تختفي من غير ما حد يعرف. الإحصائيات بتتحسب **بعد** التقطيع لصفحة، بكويري
    مجمّعة واحدة (اتنين لو الصفحة فيها حملات DM وحملات جرس مع بعض) — مش
    كويري لكل حملة.
    """
    require_permission(current_user, "announcements")

    base = db.query(Announcement)

    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        base = base.filter(or_(Announcement.title.ilike(like), Announcement.body.ilike(like)))

    wanted = (status or "all").strip().lower()
    if wanted in ALLOWED_STATUSES:
        base = base.filter(Announcement.status == wanted)

    mode = (delivery or "all").strip().lower()
    if mode == "bell":
        # الحملات القديمة اتكتبت قبل ما العمود يوجد؛ الـ server_default بيغطّي
        # الصفوف الموجودة، بس NULL بتفضل NULL لو حد كتبها بإيده.
        base = base.filter(or_(Announcement.delivery == "bell", Announcement.delivery.is_(None)))
    elif mode == "dm":
        base = base.filter(Announcement.delivery == "dm")

    total = base.with_entities(sql_func.count(Announcement.id)).scalar() or 0
    rows = (base.order_by(Announcement.created_at.desc())
            .offset(offset).limit(limit).all())

    stats = _stats_for(db, rows)

    people_ids = {r.created_by for r in rows if r.created_by} | {r.sender_id for r in rows if r.sender_id}
    names = {}
    if people_ids:
        names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(people_ids)).all()}

    return {
        "items": [
            _serialize(r, stats.get(r.id), names.get(r.created_by), names.get(r.sender_id))
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }


@router.get("/{announcement_id}")
def get_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    stats = _stats_for(db, [row])
    sender_name = None
    if row.sender_id:
        s = db.query(User.full_name).filter(User.id == row.sender_id).first()
        sender_name = s[0] if s else None
    return _serialize(row, stats.get(row.id), sender_name=sender_name)


@router.post("", status_code=201)
def create_announcement(
    data: AnnouncementSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """إنشاء مسودة. **مابيبعتش حاجة** — الإرسال ليه إندبوينت لوحده."""
    require_permission(current_user, "announcements")

    delivery = _clean_delivery(data.delivery)
    sender_id = _resolve_sender(db, current_user, delivery, data.sender_id)

    row = Announcement(
        title=(data.title or "").strip()[:160],
        body=(data.body or "").strip(),
        type=_clean_type(data.type),
        link=_clean_link(data.link),
        audience=aud.dump_filters(data.audience),
        delivery=delivery,
        sender_id=sender_id,
        status="draft",
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("📢 مسودة حملة #%s (%s) اتعملت بواسطة user_id=%s",
                row.id, delivery, current_user.id)
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

    # حملة مجدولة متقفلة على نصها عن قصد: جملة التأكيد اتكتبت على **النص ده**.
    # لو النص يتغيّر بعد التأكيد يبقى اللي وافق عليه حد هو مش اللي هيتبعت.
    if row.status in ("scheduled", "sending"):
        raise HTTPException(status_code=400,
                            detail="الحملة دي مجدولة — الغي الجدولة الأول لو عايز تعدّل")

    # حملة فشلت بس ناس استلمتها فعلاً = نفس حالة الحملة المتبعتة. لو النص
    # اتغيّر دلوقتي وكمّلنا الإرسال، نص الجمهور بياخد نص ونصه التاني بياخد نص
    # تاني — والحملة الواحدة بتبقى حملتين ومحدش يعرف مين شاف إيه. اللي لسه
    # مأثّرش على حد (فشل من غير أي تسليم) بيفضل يتعدّل عادي.
    if row.status == "failed" and _delivered_count(db, row) > 0:
        raise HTTPException(
            status_code=400,
            detail="في أعضاء استلموا النص ده خلاص — كمّل الإرسال زي ما هو، أو اعمل نسخة لو عايز تغيّره")

    delivery = _clean_delivery(data.delivery)
    sender_id = _resolve_sender(db, current_user, delivery, data.sender_id)

    row.title = (data.title or "").strip()[:160]
    row.body = (data.body or "").strip()
    row.type = _clean_type(data.type)
    row.link = _clean_link(data.link)
    row.audience = aud.dump_filters(data.audience)
    row.delivery = delivery
    row.sender_id = sender_id
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

    delivery = _clean_delivery(src.delivery)
    # النسخة حملة جديدة بتاعت اللي عملها. فلو الأصل كان بيتبعت من حساب حد
    # تاني واللي بيعمل النسخة مش الـ owner، الحساب المرسِل بيرجع له هو — مش
    # بنرمي 403.
    # السبب: "اعمل نسخة" هي المخرج من كل حالة مقفولة في الفيتشر دي، ولو هي
    # نفسها بتفشل يبقى الطريق مسدود من غير تفسير. والأدمن ده أصلاً مالوش غير
    # اختيار واحد في القايمة (نفسه)، فمفيش حاجة تلخبط.
    sender_id = src.sender_id
    if (delivery == "dm" and sender_id and sender_id != current_user.id
            and not getattr(current_user, "is_owner", False)):
        sender_id = current_user.id
    sender_id = _resolve_sender(db, current_user, delivery, sender_id)

    row = Announcement(
        title=f"{src.title} (نسخة)"[:160],
        body=src.body,
        type=src.type,
        link=src.link,
        audience=src.audience,
        delivery=delivery,
        sender_id=sender_id,
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
    """مسح المسودة. اللي وصل للأعضاء **مابيتمسحش** — `announcement_id` بيتظبط
    SET NULL في الإشعارات والرسايل، فاللي وصله حاجة بيفضل شايفها."""
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    db.delete(row)
    db.commit()
    logger.info("🗑️ حملة #%s اتمسحت بواسطة user_id=%s", announcement_id, current_user.id)


# ══════════════════════════════════════════════════════════════
#  Send
# ══════════════════════════════════════════════════════════════

def _fanout_bell(db: Session, row: Announcement, user_ids: List[int], loop) -> int:
    """صفوف إشعارات على دفعات + push للمتصلين. بيرجّع عدد اللي اتكتب."""
    written = 0
    for chunk in _chunks(user_ids, SEND_CHUNK):
        now = datetime.utcnow()
        # bulk_insert_mappings مش add_all: الـ add_all كان بيمسك صف ORM لكل عضو
        # في الـ identity map عشان يرجّع الـ ids للـ live push. على ٢٠ ألف صف ده
        # ذاكرة مدفوعة عشان حاجة محتاجينها للمتصلين بس — واللي بنقراهم تحت
        # بـ SELECT واحد مفلتر عليهم هُمّ.
        db.bulk_insert_mappings(Notification, [
            {
                "user_id": uid, "title": row.title, "body": row.body,
                "type": row.type, "link": row.link,
                "announcement_id": row.id, "is_read": False, "created_at": now,
            }
            for uid in chunk
        ])
        db.commit()
        written += len(chunk)

        # المتصلين بس هُمّ اللي محتاجين الـ id بتاعهم يترجع — الباقي هيشوفها من
        # البولينج العادي، فمفيش داعي نقرا ٢٠ ألف id عشان نبعت لـ ٣٠ واحد.
        online = [uid for uid in chunk if manager.is_online(uid)]
        if not online:
            continue
        # الـ try شايل قراءة الـ ids كمان مش الـ push بس: الصفوف اتحفظت فوق
        # خلاص، فأي فشل من هنا لتحت هو فشل في طبقة السرعة. لو طلع لبرة كان
        # هيتكتب "failed" على دفعة وصلت فعلاً.
        try:
            rows = (
                db.query(Notification.id, Notification.user_id)
                .filter(Notification.announcement_id == row.id,
                        Notification.user_id.in_(online))
                .all()
            )
            items = [_live_item(nid, uid, row) for nid, uid in rows]
            # الـ push لازم يتنفّذ على الـ loop بتاع التطبيق: الـ WebSockets
            # عايشة هناك، والثريد ده مالوش loop.
            asyncio.run_coroutine_threadsafe(_push_live(items), loop).result(timeout=60)
        except Exception:
            logger.exception("📢 حملة #%s: الـ live push فشل — الصفوف اتحفظت برضه", row.id)
    return written


def _fanout_dm(db: Session, row: Announcement, user_ids: List[int], loop) -> int:
    """محادثة خاصة لكل عضو + رسالة واحدة فيها، على دفعات.

    الخطوات هي نفس خطوات `POST /chat/dm` بالظبط (نفس `dm_service`)، بس مجمّعة:
    كويري واحدة تلاقي القنوات الموجودة، إنشاء للناقص بس، والعضويات والرسايل
    بالجملة. إعادة تشغيل نفس الحملة مابتعملش قناة تانية لنفس الزوج لأن الاسم
    متحدّد بالحسابين.
    """
    sender = db.query(User).filter(User.id == row.sender_id).first()
    if not sender:
        raise RuntimeError(f"الحملة #{row.id} وضعها DM ومفيش حساب مرسِل")

    content = _dm_body(row)
    preview = (content or "")[:60]
    written = 0

    for chunk in _chunks(user_ids, SEND_CHUNK):
        now = datetime.utcnow()
        channel_by_recipient = dm_service.ensure_dm_channels(db, sender.id, chunk)
        if not channel_by_recipient:
            db.commit()
            continue

        db.bulk_insert_mappings(Message, [
            {
                "channel_id": cid, "sender_id": sender.id, "content": content,
                "message_type": MessageType.TEXT, "announcement_id": row.id,
                "read_count": 0, "is_deleted": False, "created_at": now,
            }
            for cid in channel_by_recipient.values()
        ])
        db.commit()
        written += len(channel_by_recipient)

        # الاشتراك على السوكيت لكل طرف بقناته هو — مش للكل بكل القنوات.
        dm_service.subscribe_pairs(sender.id, channel_by_recipient)

        online = {rid: cid for rid, cid in channel_by_recipient.items() if manager.is_online(rid)}
        if not online:
            continue
        # زي مسار الجرس: الرسايل اتحفظت خلاص، واللي بعد كده طبقة سرعة.
        try:
            _dm_live_push(db, row, sender, content, preview, now, online, loop)
        except Exception:
            logger.exception("📢 حملة #%s: الـ live DM push فشل — الرسايل اتحفظت برضه", row.id)
    return written


def _dm_live_push(db: Session, row: Announcement, sender: User, content: str,
                  preview: str, now: datetime, online: Dict[int, int], loop) -> None:
    """ابعت الرسايل اللي لسه اتحفظت للمتصلين دلوقتي على السوكيت.

    بيقرا الـ ids بتاعت المتصلين بس — الباقي هيلاقي المحادثة في قايمة الرسايل
    عادي، فمفيش داعي نقرا ٢٠ ألف صف عشان نبعت لـ ٣٠ واحد.
    """
    msg_by_channel = dict(
        db.query(Message.channel_id, sql_func.max(Message.id))
        .filter(Message.announcement_id == row.id,
                Message.channel_id.in_(list(online.values())))
        .group_by(Message.channel_id)
        .all()
    )
    items = [
        {
            "user_id": rid,
            "channel_id": cid,
            "sender_name": sender.full_name,
            "preview": preview,
            "message": {
                "id": msg_by_channel.get(cid),
                "channel_id": cid,
                "channel": dm_service.dm_channel_name(sender.id, rid),
                "sender_id": sender.id,
                "sender_name": sender.full_name,
                "sender_avatar": sender.avatar_url,
                "sender_is_admin": bool(sender.is_admin),
                "content": content,
                "message_type": "text",
                "file_url": None, "file_name": None, "file_size": None,
                "reply_to_id": None,
                "created_at": now.isoformat(),
                "author_id": sender.id,
                "reactions_summary": [],
            },
        }
        for rid, cid in online.items()
    ]
    # الـ push لازم يتنفّذ على الـ loop بتاع التطبيق: الـ WebSockets عايشة
    # هناك، والثريد ده مالوش loop.
    asyncio.run_coroutine_threadsafe(_push_live_dm(items), loop).result(timeout=60)


def _notify_sender_used(db: Session, row: Announcement, delivered: int, loop) -> None:
    """قول لصاحب الحساب إن حملة خرجت من عنده (القرار ٣).

    الإشعار ده **مش** شايل `announcement_id`: لو شايله كان هيتحسب ضمن اللي
    اتسلّم في إحصائيات الحملة، والراجل ده مش من جمهورها.
    """
    if not row.sender_id or not row.sent_by or row.sender_id == row.sent_by:
        return
    actor = db.query(User.full_name).filter(User.id == row.sent_by).first()
    actor_name = actor[0] if actor else "حد من الفريق"
    body = (f"{actor_name} بعت حملة من حسابك لـ {delivered} عضو. "
            f"ردودهم هتوصلك في الرسايل الخاصة بتاعتك.")
    notif = Notification(
        user_id=row.sender_id,
        title="📤 حملة اتبعتت من حسابك",
        body=body,
        type="warning",
        link="direct-messages.html",
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # الصف اتكتب خلاص، والجرس بيلقطه في البولينج العادي. الـ push بيتعمل
    # للمتصل بس — زي كل push تاني في الملف ده، وعشان مانبنيش كوروتين أصلاً
    # لحد مش هيستقبلها.
    if not manager.is_online(row.sender_id):
        return
    try:
        asyncio.run_coroutine_threadsafe(_push_live([{
            "user_id": row.sender_id,
            "data": {"id": notif.id, "title": notif.title, "body": notif.body,
                     "type": notif.type, "link": notif.link, "is_read": False},
        }]), loop).result(timeout=30)
    except Exception:
        logger.debug("📢 حملة #%s: إشعار صاحب الحساب اتسجّل بس مالحقش الـ push", row.id)


def _run_real_send(announcement_id: int, user_ids: List[int], loop) -> None:
    """الفان-آوت الحقيقي — بيشتغل في ثريد، مش جوّه الريكوست.

    السبب هو نفس سبب حملات الإيميل بالحرف (شوف docstring بتاع
    email_campaigns.py): nginx بيقطع أي ريكوست على `/api/` بعد ١٢٠ ثانية
    (`proxy_read_timeout`)، وأي شغل طويل جوّه الـ event loop بيجمّد الموقع كله
    مش الريكوست ده بس. على ١٩١٥ عضو فان-آوت الجرس بيخلص في أقل من ثانية —
    بس فان-آوت الـ DM بيكتب في ٣ جداول لكل عضو، والثريد هنا بيبقى الفرق بين
    إرسالة عادية وموقع واقف.

    الثريد ليه جلسة DB بتاعته: جلسة الريكوست بتتقفل أول ما الريكوست يرجّع.

    قايمة `user_ids` جاية متصفّاة خلاص من `_begin_real_send` (اللي استلموا
    اتشالوا في حالة الإكمال)، فممكن تكون فاضية — ودي حالة صحيحة معناها إن
    الحملة كانت وصلت كلها وبس الحالة هي اللي كانت غلط.
    """
    db = SessionLocal()
    try:
        row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
        if not row:
            logger.warning("📢 حملة #%s اختفت قبل ما الإرسال يبدأ", announcement_id)
            return

        if (row.delivery or "bell") == "dm":
            written = _fanout_dm(db, row, user_ids, loop)
        else:
            written = _fanout_bell(db, row, user_ids, loop)

        row.status = "sent"
        row.sent_at = datetime.utcnow()
        row.failure_reason = None
        db.commit()

        # مقصود إنها جوّه try لوحدها: الحملة **وصلت** خلاص واتقفلت على "sent"
        # فوق. لو إشعار صاحب الحساب فشل بعد كده والاستثناء طلع لبرة، الـ
        # except اللي تحت كان هيكتب "failed" على حملة اتسلّمت بالكامل — وهي
        # بالظبط الحالة اللي كانت بتخلي إعادة الإرسال توصل للناس مرتين.
        try:
            _notify_sender_used(db, row, _delivered_count(db, row), loop)
        except Exception:
            logger.exception("📢 حملة #%s: إشعار صاحب الحساب فشل — الحملة اتبعتت برضه",
                             announcement_id)

        logger.info("📢 حملة #%s (%s) اتبعتت — %s صف جديد",
                    announcement_id, row.delivery or "bell", written)

    except Exception as exc:
        logger.exception("📢 حملة #%s فشلت في الخلفية", announcement_id)
        try:
            db.rollback()
            row = db.query(Announcement).filter(Announcement.id == announcement_id).first()
            if row:
                row.status = "failed"
                # السبب بيتكتب عشان الكارت الأحمر يقول حاجة. الطول محدود لأن
                # العمود محدود، والرسالة الكاملة موجودة في اللوج فوق.
                row.failure_reason = f"{type(exc).__name__}: {exc}"[:300]
                db.commit()
        except Exception:
            logger.exception("📢 حملة #%s: مقدرناش نسجّل إنها failed", announcement_id)
    finally:
        db.close()
        # الحالة الجوّه-بروسيس بتتصفّر قبل القفل ما يتفك، عشان أي بولينج جاي
        # مايشوفش "بتتبعت" وهي خلصت.
        _active_send.update(running=False, announcement_id=None, total=0, started_at=None)
        _send_lock.release()


def _begin_real_send(db: Session, row: Announcement, loop, *,
                     actor_id: Optional[int] = None) -> Dict[str, Any]:
    """Resolve the audience, mark the row sending and hand off to a thread.

    Shared by the send endpoint and the scheduler job so a scheduled campaign
    goes out through exactly the same path as one sent by hand — a second
    implementation is a second set of bugs.

    Caller must already hold `_send_lock`; the worker releases it. That holds
    even when there is nothing left to send: the thread still starts, writes
    nothing and closes the campaign out, so the lock has exactly one owner on
    every path rather than a special case nobody remembers.

    Resume (decision 1 in the module docstring): when the campaign is being
    retried, everybody who already holds a row for it is removed from this
    run. On a first send there is nothing to resume, and the filter is not
    applied — it would otherwise swallow the test row the operator sent
    themselves on purpose.
    """
    filters = aud.load_filters(row.audience)
    users = aud.resolve_users(db, filters)
    if not users:
        raise HTTPException(status_code=400, detail="الفلتر ده مالوش أي عضو — عدّله وجرّب تاني")

    user_ids = [u.id for u in users]
    audience_size = len(user_ids)

    if (row.delivery or "bell") == "dm":
        if not row.sender_id:
            raise HTTPException(status_code=400, detail="حملة الرسايل الخاصة محتاجة تحدد الحساب المرسِل")
        # الحساب لازم يكون **لسه** أدمن دلوقتي، مش وقت الحفظ. الحملة المجدولة
        # بتوصل هنا من الـ scheduler من غير ما تعدّي على `_resolve_sender`،
        # فلو الشخص اتشال منه الأدمن بين الجدولة والإرسال دي آخر نقطة تمسك
        # الحاجة دي قبل ما آلاف الرسايل تخرج من حساب مابقاش أدمن.
        sender = db.query(User).filter(User.id == row.sender_id).first()
        if not sender or not (sender.is_admin or sender.is_owner):
            raise HTTPException(
                status_code=400,
                detail="الحساب المرسِل مابقاش أدمن — اختار حساب تاني قبل ما تبعت")
        # محدش بيبعت لنفسه: قناة `dm_x_x` مالهاش وجود، ولو سبناه في الجمهور
        # كان هيفضل "لسه ماستلمش" في كل إعادة إرسال للأبد.
        user_ids = [uid for uid in user_ids if uid != row.sender_id]

    resuming = row.status in ("failed", "sending")
    skipped = 0
    if resuming:
        already = _delivered_user_ids(db, row)
        if already:
            before = len(user_ids)
            user_ids = [uid for uid in user_ids if uid not in already]
            skipped = before - len(user_ids)

    row.status = "sending"
    row.recipients_count = audience_size
    row.failure_reason = None
    if actor_id is not None:
        row.sent_by = actor_id
    db.commit()

    _active_send.update(running=True, announcement_id=row.id, total=len(user_ids),
                        started_at=datetime.utcnow().isoformat())
    threading.Thread(
        target=_run_real_send,
        args=(row.id, user_ids, loop),
        name=f"announcement-send-{row.id}",
        daemon=True,
    ).start()
    return {"audience": audience_size, "pending": len(user_ids),
            "skipped": skipped, "resuming": resuming}


def _send_test(db: Session, row: Announcement, actor: User) -> Dict[str, Any]:
    """التست بيروح للمرسِل هو بس — بنفس وضع التسليم بتاع الحملة.

    السبب إن التست موجود أصلاً: اللي بيتوافق عليه لازم يكون بالظبط اللي العضو
    هيشوفه. تست حملة DM كإشعار جرس بيوافق على حاجة تانية.
    """
    delivery = row.delivery or "bell"

    if delivery == "dm":
        sender_id = _resolve_sender(db, actor, "dm", row.sender_id)
        if sender_id == actor.id:
            # مفيش محادثة خاصة بين الشخص ونفسه (`dm_x_x` مش موجودة)، والاختراع
            # هنا كان هيعمل تريد الواحد فيه بيكلّم نفسه في قايمة رسايله. بنقول
            # اللي حصل بالظبط بدل ما نسكت.
            notif = Notification(
                user_id=actor.id, title=row.title, body=row.body,
                type=row.type, link=row.link, announcement_id=row.id, is_read=False,
            )
            db.add(notif)
            db.commit()
            db.refresh(notif)
            return {
                "mode": "test", "delivery": "bell", "delivered": 1,
                "live": [_live_item(notif.id, actor.id, row)],
                "message": ("إنت المرسِل نفسه، ومفيش محادثة خاصة بين الواحد ونفسه — "
                            "بعتنالك النص في الجرس. اختار حساب مرسِل تاني لو عايز "
                            "تشوفها كرسالة خاصة."),
            }

        ch, _created = dm_service.get_or_create_dm_channel(db, sender_id, actor.id)
        sender = db.query(User).filter(User.id == sender_id).first()
        content = _dm_body(row)
        msg = Message(
            channel_id=ch.id, sender_id=sender_id, content=content,
            message_type=MessageType.TEXT, announcement_id=row.id,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return {
            "mode": "test", "delivery": "dm", "delivered": 1,
            "live_dm": [{
                "user_id": actor.id,
                "channel_id": ch.id,
                "sender_name": sender.full_name if sender else "",
                "preview": (content or "")[:60],
                "message": {
                    "id": msg.id, "channel_id": ch.id, "channel": ch.name,
                    "sender_id": sender_id,
                    "sender_name": sender.full_name if sender else "",
                    "sender_avatar": sender.avatar_url if sender else None,
                    "sender_is_admin": bool(sender.is_admin) if sender else False,
                    "content": content, "message_type": "text",
                    "file_url": None, "file_name": None, "file_size": None,
                    "reply_to_id": None,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "author_id": sender_id, "reactions_summary": [],
                },
            }],
            "message": "الحملة اتبعتت ليك إنت بس كرسالة خاصة — شوفها في الرسايل",
        }

    notif = Notification(
        user_id=actor.id, title=row.title, body=row.body,
        type=row.type, link=row.link, announcement_id=row.id, is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return {
        "mode": "test", "delivery": "bell", "delivered": 1,
        "live": [_live_item(notif.id, actor.id, row)],
        "message": "الحملة اتبعتت ليك إنت بس — شوفها في الجرس",
    }


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
        result = _send_test(db, row, current_user)
        # التست بيفضل synchronous: صف واحد، ومحدش مستني غير اللي ضغط.
        live = result.pop("live", None)
        live_dm = result.pop("live_dm", None)
        if live:
            await _push_live(live)
        if live_dm:
            await _push_live_dm(live_dm)
        return result

    # ── حقيقي ──
    if (payload.confirm_phrase or "").strip() != CONFIRM_PHRASE:
        raise HTTPException(status_code=400, detail=f'الإرسال الحقيقي محتاج تكتب "{CONFIRM_PHRASE}" بالظبط')

    if row.status == "sent":
        raise HTTPException(status_code=400, detail="الحملة دي اتبعتت خلاص — اعمل نسخة لو عايز تبعتها تاني")

    # الحساب المرسِل بيتفحص من تاني هنا مش بس وقت الحفظ: ممكن يكون اتشال من
    # الأدمن، أو الحملة اتحفظت وقت ما اللي بيبعت كان الـ owner واللي بيضغط
    # دلوقتي أدمن عادي.
    if (row.delivery or "bell") == "dm":
        row.sender_id = _resolve_sender(db, current_user, "dm", row.sender_id)
        db.commit()

    if not _send_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="في حملة بتتبعت دلوقتي — استنى لما تخلص")

    # القفل بيتاخد هنا وبيتفك في الثريد، مش في الريكوست: الإرسال بيفضل شغّال
    # بعد ما الريكوست يرجّع، فلو فكّيناه هنا تاني ضغطة كانت هتبدأ إرسالة موازية.
    #
    # ملحوظة: الوصول لهنا وإحنا ماسكين القفل معناه إن مفيش ثريد شغّال. يعني
    # لو الحالة "sending" فالوركر مات وهو بيبعت — وde هي بالظبط الحالة اللي
    # `_begin_real_send` بيكمّلها بدل ما يبدأ من الأول.
    try:
        outcome = _begin_real_send(db, row, asyncio.get_running_loop(),
                                   actor_id=current_user.id)
    except Exception:
        # أي فشل قبل ما الثريد يقوم لازم يفك القفل هنا — مفيش حد تاني هيفكّه.
        # الـ finally حوالين محاولة الإصلاح مقصود: لو الـ rollback نفسه رمى،
        # القفل لازم يتفك برضه وإلا التاب بيقفل على 409 للأبد.
        try:
            db.rollback()
            stuck = db.query(Announcement).filter(Announcement.id == announcement_id).first()
            if stuck and stuck.status == "sending":
                stuck.status = "draft"
                db.commit()
        except Exception:
            logger.exception("📢 حملة #%s: مقدرناش نرجّعها draft بعد فشل البداية", announcement_id)
        finally:
            _send_lock.release()
        raise

    pending, skipped = outcome["pending"], outcome["skipped"]
    logger.info("📢 حملة #%s بدأت الإرسال لـ %s عضو (%s استلموا قبل كده) بواسطة user_id=%s",
                row.id, pending, skipped, current_user.id)

    if outcome["resuming"]:
        message = (f"بنكمّل الحملة: {pending} عضو لسه، و{skipped} استلموها قبل كده"
                   if pending else
                   f"كل الـ {skipped} عضو استلموها خلاص — بنقفل الحملة على أنها اتبعتت")
    else:
        message = f"بدأ الإرسال لـ {pending} عضو في الخلفية"

    # بيرجّع على طول والحالة لسه "sending" — التاب بيـ poll الحالة تحت.
    return {"mode": "real", "started": True, "delivered": pending,
            "audience": outcome["audience"], "skipped": skipped,
            "resuming": outcome["resuming"], "delivery": row.delivery or "bell",
            "status": "sending", "message": message}


@router.post("/{announcement_id}/schedule")
def schedule_announcement(
    announcement_id: int,
    payload: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """اجدول الحملة تتبعت في وقت معيّن.

    جملة التأكيد بتتكتب هنا، مش وقت ما الـ job يشتغل. قرار إن ده يروح لكل
    الأعضاء لازم يتاخد وفي حد واقف قدام الشاشة — الساعة ٨ بالليل مفيش حد.
    الجمهور نفسه بيتحلّ وقت الإرسال زي أي إرسالة عادية، عشان فلتر زي
    "اشتراكه بيخلص خلال ٧ أيام" يفضل معناه واحد.

    ولنفس السبب `sent_by` بيتكتب هنا: اللي "بعت" الحملة دي فعلاً هو اللي
    اتخذ القرار وكتب جملة التأكيد، مش الـ scheduler.

    ولو فات ميعادها بأكتر من `SCHEDULE_GRACE` مابتتبعتش أصلاً — القرار ٢ في
    الدوكسترينج بتاع الملف.
    """
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    _require_sendable(row)

    if row.status in ("sent", "sending"):
        raise HTTPException(status_code=400, detail="الحملة دي اتبعتت خلاص — اعمل نسخة لو عايز تبعتها تاني")

    if (payload.confirm_phrase or "").strip() != CONFIRM_PHRASE:
        raise HTTPException(status_code=400, detail=f'الجدولة محتاجة تكتب "{CONFIRM_PHRASE}" بالظبط')

    if (row.delivery or "bell") == "dm":
        row.sender_id = _resolve_sender(db, current_user, "dm", row.sender_id)

    raw = (payload.scheduled_for or "").strip()
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="التاريخ مش مفهوم")

    # الفرونت بيبعت وقت بتوقيت المستخدم؛ التخزين UTC ساذج زي باقي الجدول.
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)

    if when <= datetime.utcnow() + timedelta(minutes=1):
        raise HTTPException(status_code=400, detail="لازم تجدولها بعد دقيقة على الأقل من دلوقتي")

    row.scheduled_for = when
    row.status = "scheduled"
    row.sent_by = current_user.id
    row.failure_reason = None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    logger.info("📅 حملة #%s اتجدولت لـ %s بواسطة user_id=%s", row.id, when, current_user.id)
    return _serialize(row)


@router.post("/{announcement_id}/unschedule")
def unschedule_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ارجّع الحملة المجدولة مسودة. لازم يكون في طريق للتراجع قبل ما توصل."""
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    if row.status != "scheduled":
        raise HTTPException(status_code=400, detail="الحملة دي مش مجدولة")
    row.scheduled_for = None
    row.status = "draft"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    logger.info("📅 حملة #%s اتلغت جدولتها بواسطة user_id=%s", row.id, current_user.id)
    return _serialize(row)


@router.get("/{announcement_id}/status")
def send_status(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حالة الإرسال — عشان التاب يفرّق بين حملة بتتبعت دلوقتي وحملة واقفة.

    عمود `status` في الداتابيز هو المصدر اللي بيعيش بعد أي restart؛ و
    `sending_active` بيقول إن في ثريد فعلاً شغّال عليها في اللحظة دي. الاتنين
    مع بعض بيمسكوا الحالة الوحيدة اللي الـ status لوحده مش بيوصفها: "sending"
    من غير ثريد شغّال يبقى الوركر وقع في نص الإرسال — ودي بقت حالة يتكمّل
    منها دلوقتي، مش طريق مسدود (القرار ١).
    """
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)
    delivered = _delivered_count(db, row)
    active = bool(_active_send["running"] and _active_send["announcement_id"] == row.id)
    stalled = bool(row.status == "sending" and not active)
    return {
        "id": row.id,
        "status": row.status,
        "delivery": row.delivery or "bell",
        "sending_active": active,
        "recipients_count": row.recipients_count or 0,
        "delivered": delivered,
        "sent_at": row.sent_at,
        "failure_reason": row.failure_reason,
        "stalled": stalled,
        # اللي الشاشة محتاجة تعرفه عشان تعرض "كمّل" بدل "الحملة وقعت وخلاص".
        "resumable": bool(row.status == "failed" or stalled),
    }


@router.get("/{announcement_id}/recipients")
def list_recipients(
    announcement_id: int,
    state: str = Query("all"),                       # all | read | unread
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """مين استلم الحملة دي، ومين فتحها.

    أول سؤال بيتسأل على نسبة قراءة واطية هو "مين اللي مافتحهاش" — والرقم لوحده
    مابيجاوبش عليه. الداتا موجودة أصلاً: الصفوف اللي شايلة الـ id ده مربوطة
    باليوزرز، فمحتاجة endpoint مش جدول جديد.

    الوضعين بيتقروا من جدولين مختلفين (`notifications` للجرس، `messages`
    للرسايل الخاصة) بس بيرجّعوا نفس الشكل بالظبط، عشان الدرج في الواجهة يفضل
    درج واحد.

    بصفحات: حملة لـ ٢٠ ألف عضو مالهاش لازمة تترمي كلها في ريسبونس واحد.
    """
    require_permission(current_user, "announcements")
    row = _get_or_404(db, announcement_id)

    if (row.delivery or "bell") == "dm":
        return _recipients_dm(db, row, state, search, limit, offset)
    return _recipients_bell(db, row, state, search, limit, offset)


def _recipients_bell(db: Session, row: Announcement, state: str, search: Optional[str],
                     limit: int, offset: int) -> Dict[str, Any]:
    base = (
        db.query(Notification, User)
        .join(User, User.id == Notification.user_id)
        .filter(Notification.announcement_id == row.id)
    )

    if state == "read":
        base = base.filter(Notification.is_read.is_(True))
    elif state == "unread":
        base = base.filter(Notification.is_read.is_(False))

    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        base = base.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))

    total = base.with_entities(sql_func.count(Notification.id)).scalar() or 0

    # العدّادات دي على الحملة كلها، مش على الصفحة ولا على الفلتر — عشان الهيدر
    # يفضل ثابت وإنت بتقلب بين "اتقرت" و"مافتحهاش".
    totals = dict(
        db.query(Notification.is_read, sql_func.count(Notification.id))
        .filter(Notification.announcement_id == row.id)
        .group_by(Notification.is_read)
        .all()
    )
    read_count = int(totals.get(True, 0))
    unread_count = int(totals.get(False, 0))

    rows = (
        base.order_by(Notification.is_read.asc(), User.full_name.asc())
        .offset(offset).limit(limit).all()
    )

    return {
        "announcement_id": row.id,
        "delivery": "bell",
        "total": total,
        "delivered": read_count + unread_count,
        "read": read_count,
        "unread": unread_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "items": [
            {
                "user_id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "avatar_url": u.avatar_url,
                "is_read": bool(n.is_read),
                "sent_at": n.created_at,
            }
            for n, u in rows
        ],
    }


def _recipients_dm(db: Session, row: Announcement, state: str, search: Optional[str],
                   limit: int, offset: int) -> Dict[str, Any]:
    """نفس الشكل، بس مقروء من الرسايل وإيصالات قراءتها.

    "اتقرت" = فيه صف `MessageRead` من العضو (مش من المرسِل) على الرسالة —
    نفس الآلية اللي الشات بيستخدمها أصلاً، مش آلية تانية اتخترعت للحملات.
    """
    read_exists = (
        db.query(MessageRead.message_id)
        .filter(MessageRead.message_id == Message.id,
                MessageRead.user_id == ChatMember.user_id)
        .exists()
    )

    base = (
        db.query(Message, User, read_exists.label("is_read"))
        .join(ChatMember, ChatMember.channel_id == Message.channel_id)
        .join(User, User.id == ChatMember.user_id)
        .filter(Message.announcement_id == row.id,
                ChatMember.user_id != Message.sender_id)
    )

    if state == "read":
        base = base.filter(read_exists)
    elif state == "unread":
        base = base.filter(~read_exists)

    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        base = base.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))

    total = base.with_entities(sql_func.count(Message.id)).scalar() or 0

    counted = (
        db.query(read_exists.label("is_read"), sql_func.count(Message.id))
        .select_from(Message)
        .join(ChatMember, ChatMember.channel_id == Message.channel_id)
        .filter(Message.announcement_id == row.id,
                ChatMember.user_id != Message.sender_id)
        .group_by(read_exists)
        .all()
    )
    totals = {bool(k): int(v) for k, v in counted}
    read_count = totals.get(True, 0)
    unread_count = totals.get(False, 0)

    rows = (
        base.order_by(read_exists.asc(), User.full_name.asc())
        .offset(offset).limit(limit).all()
    )

    return {
        "announcement_id": row.id,
        "delivery": "dm",
        "total": total,
        "delivered": read_count + unread_count,
        "read": read_count,
        "unread": unread_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "items": [
            {
                "user_id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "avatar_url": u.avatar_url,
                "is_read": bool(is_read),
                "sent_at": m.created_at,
            }
            for m, u, is_read in rows
        ],
    }
