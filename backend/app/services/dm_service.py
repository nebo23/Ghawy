# -*- coding: utf-8 -*-
"""
dm_service.py — الرسائل الخاصة: القناة بتتعمل من هنا وبس.

القناة الخاصة بين اتنين اسمها متحدّد بالحساب: `dm_{الأصغر}_{الأكبر}`. الاسم ده
هو اللي بيمنع نفس الاتنين يبقى بينهم أكتر من محادثة — يعني لازم يبقى **تعريف
واحد** في المشروع كله. لو اتنسخ في مكان تاني واتغيّر في واحد منهم، النتيجة
مابتبقاش خطأ ظاهر: بتبقى محادثتين بين نفس الشخصين، ومحدش بياخد باله غير لما
عضو يسأل ليه عنده تريدين مع نفس الشخص.

عشان كده الملف ده فيه الحاجتين مع بعض:
  • `get_or_create_dm_channel` — زوج واحد (اللي `POST /chat/dm` بيستخدمه).
  • `ensure_dm_channels` — عدد كبير من الأزواج دفعة واحدة (حملات الـ DM).
الاتنين بينادوا نفس `dm_channel_name`، فمفيش نسختين يقدروا يفترقوا.

ملاحظة أمان: أي مسار بيعمل INSERT في `chat_members` بيدي حد حق دخول محادثة.
الدوال هنا بتاخد الأطراف كـ ids من الكود اللي نده — مابتقراش أي حاجة من
ريكوست. اللي بينده هو المسؤول إن الـ ids دي مقصودة فعلاً.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Channel, ChannelType, ChatMember, MemberRole
from app.services.ws_manager import manager

logger = logging.getLogger("ghawy.dm")


def dm_channel_name(user_a_id: int, user_b_id: int) -> str:
    """اسم القناة الخاصة بين الاتنين دول — نفس الاسم مهما كان الترتيب."""
    low, high = sorted((int(user_a_id), int(user_b_id)))
    return f"dm_{low}_{high}"


def find_dm_channel(db: Session, user_a_id: int, user_b_id: int) -> Optional[Channel]:
    """القناة الموجودة بين الاتنين، أو None."""
    return (
        db.query(Channel)
        .filter(Channel.name == dm_channel_name(user_a_id, user_b_id),
                Channel.channel_type == ChannelType.DM)
        .first()
    )


def get_or_create_dm_channel(db: Session, user_a_id: int, user_b_id: int) -> Tuple[Channel, bool]:
    """رجّع قناة الاتنين دول، واعملها لو مش موجودة. بيرجّع (القناة, اتعملت دلوقتي؟).

    بيعمل commit — الشكل ده هو اللي المسار الأصلي في `chat.py` كان عليه، وأي
    حد بينده الدالة بيتوقع الصف يبقى موجود لما ترجع.
    """
    if int(user_a_id) == int(user_b_id):
        raise ValueError("Cannot DM yourself")

    ch = find_dm_channel(db, user_a_id, user_b_id)
    if ch:
        return ch, False

    ch = Channel(name=dm_channel_name(user_a_id, user_b_id), channel_type=ChannelType.DM)
    db.add(ch)
    db.commit()
    db.refresh(ch)

    db.add(ChatMember(channel_id=ch.id, user_id=user_a_id, role=MemberRole.MEMBER))
    db.add(ChatMember(channel_id=ch.id, user_id=user_b_id, role=MemberRole.MEMBER))
    db.commit()

    manager.subscribe(user_a_id, [ch.id])
    manager.subscribe(user_b_id, [ch.id])
    return ch, True


def ensure_dm_channels(db: Session, sender_id: int,
                       recipient_ids: Iterable[int]) -> Dict[int, int]:
    """نفس خطوات الدالة اللي فوق بالظبط، بس لعدد كبير من الأزواج مرة واحدة.

    بترجّع `{recipient_id: channel_id}`.

    ليه مش لوپ على `get_or_create_dm_channel`: حملة لـ ١٩١٥ عضو كانت هتبقى
    ١٩١٥ SELECT + ١٩١٥ INSERT + ٣٨٣٠ INSERT تانية، كل واحد منهم رحلة لوحده
    للداتابيز. هنا: SELECT واحد للموجود، INSERT واحد للناقص، SELECT واحد
    يجيب الـ ids، وINSERT واحد للعضويات.

    الأزواج اللي قنواتهم موجودة أصلاً مابيتعملهاش حاجة — عشان إعادة تشغيل نفس
    الحملة ماتعملش محادثة تانية لنفس الشخصين.
    """
    wanted: Dict[int, str] = {}
    for rid in recipient_ids:
        rid = int(rid)
        if rid == int(sender_id):
            continue                      # محدش بيبعت لنفسه
        wanted[rid] = dm_channel_name(sender_id, rid)
    if not wanted:
        return {}

    names = list(set(wanted.values()))
    # `channels.name` مش unique في السكيمة، فممكن نظرياً يرجع أكتر من صف لنفس
    # الاسم. بناخد الأقدم (أصغر id) — نفس اللي `.first()` بيعمله في مسار الزوج
    # الواحد، عشان الاتنين يوصلوا لنفس القناة.
    by_name: Dict[str, int] = {}
    for cid, cname in (
        db.query(Channel.id, Channel.name)
        .filter(Channel.name.in_(names), Channel.channel_type == ChannelType.DM)
        .order_by(Channel.id.asc())
        .all()
    ):
        by_name.setdefault(cname, cid)

    missing = [n for n in names if n not in by_name]
    if missing:
        now = datetime.utcnow()
        db.bulk_insert_mappings(Channel, [
            {"name": n, "channel_type": ChannelType.DM, "created_at": now}
            for n in missing
        ])
        db.flush()
        for cid, cname in (
            db.query(Channel.id, Channel.name)
            .filter(Channel.name.in_(missing), Channel.channel_type == ChannelType.DM)
            .order_by(Channel.id.asc())
            .all()
        ):
            by_name.setdefault(cname, cid)

        # العضويات للقنوات الجديدة بس. القنوات القديمة أطرافها موجودة خلاص،
        # وإضافة صف تاني كانت هتعمل عضوية مكررة.
        new_ids = [by_name[n] for n in missing if n in by_name]
        rows: List[dict] = []
        rid_by_channel = {by_name[name]: rid for rid, name in wanted.items() if name in by_name}
        for cid in new_ids:
            rid = rid_by_channel.get(cid)
            if rid is None:
                continue
            rows.append({"channel_id": cid, "user_id": int(sender_id),
                         "role": MemberRole.MEMBER, "joined_at": now})
            rows.append({"channel_id": cid, "user_id": rid,
                         "role": MemberRole.MEMBER, "joined_at": now})
        if rows:
            db.bulk_insert_mappings(ChatMember, rows)
        db.flush()

    return {rid: by_name[name] for rid, name in wanted.items() if name in by_name}


def subscribe_pairs(sender_id: int, channel_by_recipient: Dict[int, int]) -> None:
    """اربط كل طرف بقناته هو على السوكيت.

    ⚠️ كل عضو بيتربط بقناته **هو بس**. `manager.subscribe` بيحط اليوزر في
    الاشتراكات اللي بيتبعت لها الـ broadcast، فلو عدّينا كل القنوات لكل عضو
    كان كل واحد هيستقبل رسايل المحادثات الخاصة بتاعت الناس التانية. المرسِل
    لوحده هو اللي بيتربط بالقنوات كلها — لأنه فعلاً طرف في كل واحدة فيهم.

    طبقة سرعة مش طبقة تسليم: الصفوف اتحفظت خلاص، واللي مش متصل هيلاقي
    المحادثة في قايمة الرسايل عادي أول ما يفتح.
    """
    try:
        manager.subscribe(int(sender_id), list(channel_by_recipient.values()))
    except Exception:
        logger.debug("subscribe فشل للمرسِل %s — الرسايل متسجّلة برضه", sender_id)

    for rid, cid in channel_by_recipient.items():
        try:
            manager.subscribe(int(rid), [cid])
        except Exception:
            logger.debug("subscribe فشل لليوزر %s — الرسالة متسجّلة برضه", rid)
