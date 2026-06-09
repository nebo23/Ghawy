from collections import defaultdict
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ChatMember, ChatMessageReaction, Message


ALLOWED_REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🙏"]


def user_can_access_message(db: Session, message: Message, user_id: int) -> bool:
    return db.query(ChatMember.id).filter(
        ChatMember.channel_id == message.channel_id,
        ChatMember.user_id == user_id,
    ).first() is not None


def set_message_reaction(
    db: Session,
    *,
    message_id: int,
    user_id: int,
    emoji: str,
    action: str,
) -> Message:
    if emoji not in ALLOWED_REACTION_EMOJIS:
        raise ValueError("Unsupported reaction emoji")

    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False,
    ).first()
    if not message:
        raise LookupError("Message not found")

    if not user_can_access_message(db, message, user_id):
        raise PermissionError("User is not a member of this channel")

    existing = db.query(ChatMessageReaction).filter(
        ChatMessageReaction.message_id == message_id,
        ChatMessageReaction.user_id == user_id,
    ).first()

    if action == "remove":
        if existing and existing.emoji == emoji:
            db.delete(existing)
    elif action == "add":
        if existing:
            existing.emoji = emoji
        else:
            db.add(ChatMessageReaction(message_id=message_id, user_id=user_id, emoji=emoji))
    else:
        raise ValueError("Reaction action must be add or remove")

    db.commit()
    return message


def get_reaction_summary(db: Session, message_id: int, user_id: int) -> list[dict]:
    counts = dict(
        db.query(ChatMessageReaction.emoji, func.count(ChatMessageReaction.id))
        .filter(ChatMessageReaction.message_id == message_id)
        .group_by(ChatMessageReaction.emoji)
        .all()
    )
    mine = {
        emoji for (emoji,) in db.query(ChatMessageReaction.emoji)
        .filter(
            ChatMessageReaction.message_id == message_id,
            ChatMessageReaction.user_id == user_id,
        )
        .all()
    }

    return [
        {
            "emoji": emoji,
            "count": int(counts.get(emoji, 0)),
            "user_reacted": emoji in mine,
        }
        for emoji in ALLOWED_REACTION_EMOJIS
        if counts.get(emoji, 0) or emoji in mine
    ]


def get_reaction_summaries(db: Session, message_ids: Iterable[int], user_id: int) -> dict[int, list[dict]]:
    ids = list(message_ids)
    if not ids:
        return {}

    counts_by_message = defaultdict(dict)
    rows = (
        db.query(ChatMessageReaction.message_id, ChatMessageReaction.emoji, func.count(ChatMessageReaction.id))
        .filter(ChatMessageReaction.message_id.in_(ids))
        .group_by(ChatMessageReaction.message_id, ChatMessageReaction.emoji)
        .all()
    )
    for message_id, emoji, count in rows:
        counts_by_message[message_id][emoji] = int(count)

    mine_by_message = defaultdict(set)
    mine_rows = (
        db.query(ChatMessageReaction.message_id, ChatMessageReaction.emoji)
        .filter(
            ChatMessageReaction.message_id.in_(ids),
            ChatMessageReaction.user_id == user_id,
        )
        .all()
    )
    for message_id, emoji in mine_rows:
        mine_by_message[message_id].add(emoji)

    summaries = {}
    for message_id in ids:
        counts = counts_by_message.get(message_id, {})
        mine = mine_by_message.get(message_id, set())
        summaries[message_id] = [
            {
                "emoji": emoji,
                "count": counts.get(emoji, 0),
                "user_reacted": emoji in mine,
            }
            for emoji in ALLOWED_REACTION_EMOJIS
            if counts.get(emoji, 0) or emoji in mine
        ]

    return summaries
