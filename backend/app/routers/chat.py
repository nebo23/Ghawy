"""
Chat Router — Channels, Messages (REST), File Uploads, Read Receipts, Delete
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, text as sqltext
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.services.ws_manager import manager
from app.models import User, Channel, ChatMember, Message, MessageRead, MemberRole, ChannelType, MessageType, Post, PostChannelRead
from app.schemas import ChannelCreate, ChannelOut, MessageCreate, MessageOut, ChatMemberOut
from app.routers.users import get_current_user, get_current_active_member
from app.services.file_service import save_upload
from app.services.attachments import resolve_attachment, InvalidAttachment
from app.services.chat_reactions import get_reaction_summaries
from app.services.mentions_service import process_admin_mentions
from pydantic import BaseModel

import json
import os
from pathlib import Path as FilePath

router = APIRouter(prefix="/chat", tags=["Chat"])


# ── Who is allowed inside a channel ──────────────────────────────────────────
#
# The community channels are open by design: any active member may read and
# post in them, and the first read auto-creates their membership row. A DM is
# the opposite — it belongs to exactly the two people /chat/dm put in it.
#
# That distinction was never enforced. Reading a channel auto-joined the caller
# to *any* id, DMs included, so an active member could walk the sequential
# channel ids and read every private conversation on the site — and, having
# been auto-joined, keep receiving them live over the WebSocket. Posting and
# the member roster checked nothing at all.
#
# So membership for a DM is now a precondition rather than something a request
# grants itself. `ensure_channel_access` is the single gate; every read, write
# and roster path calls it, and the DM branch never creates a membership row.
def ensure_channel_access(db: Session, channel_id: int, user: User, *, auto_join: bool = False):
    """Return the channel if `user` may use it, else raise 403/404.

    `auto_join=True` creates the membership row for an open community channel
    (the historical behaviour of the read path). It never applies to a DM: a
    request must not be able to make itself a participant in someone else's
    conversation.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    membership = db.query(ChatMember).filter(
        ChatMember.channel_id == channel_id,
        ChatMember.user_id == user.id,
    ).first()

    if channel.channel_type == ChannelType.DM:
        if not membership:
            # 404, not 403: confirming that a DM exists between two named
            # people is itself the thing being protected here.
            raise HTTPException(status_code=404, detail="Channel not found")
        return channel

    if not membership and auto_join:
        membership = ChatMember(channel_id=channel_id, user_id=user.id, role=MemberRole.MEMBER)
        db.add(membership)
        db.commit()
        manager.subscribe(user.id, [channel_id])

    return channel


BACKEND_DIR = FilePath(__file__).resolve().parent.parent.parent
START_HERE_CONFIG = BACKEND_DIR / "static" / "config" / "start_here.json"


class StartHereConfigUpdate(BaseModel):
    video_url: str


@router.get("/start-here-config")
def get_start_here_config(
    current_user: User = Depends(get_current_active_member),
):
    try:
        if START_HERE_CONFIG.exists():
            with open(START_HERE_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"video_url": data.get("video_url", "")}
    except Exception:
        pass
    return {"video_url": ""}


@router.put("/start-here-config")
def update_start_here_config(
    data: StartHereConfigUpdate,
    current_user: User = Depends(get_current_active_member),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        START_HERE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(START_HERE_CONFIG, "w", encoding="utf-8") as f:
            json.dump({"video_url": data.video_url}, f)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Simple Message Create Schema ────────────────────────────
class SimpleMsgCreate(BaseModel):
    channel: str = "general"
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None


# Mirrors MAX_MESSAGE_CHARS in routers/ws.py — the two paths write the same table.
MAX_MESSAGE_CHARS = 4000


# ─── GET /chat/messages — simple flat endpoint ───────────────
@router.get("/messages")
def get_messages_simple(
    channel: str = Query("general"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    ch = db.query(Channel).filter(Channel.name == channel).first()
    if not ch:
        return []

    # DM channels are named dm_{low}_{high}, so without this check any member
    # could read anyone's private conversation by guessing an id pair. This is
    # the same gate every other read path uses; it refuses a DM to a
    # non-participant and 404s rather than confirming the conversation exists.
    # auto_join stays off: reading a channel must not make you a member of it.
    ensure_channel_access(db, ch.id, current_user)

    msgs = (
        db.query(Message)
        .filter(Message.channel_id == ch.id, Message.is_deleted == False)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .all()
    )
    msgs.reverse()

    if not msgs:
        return []

    # ── Batch load all senders in one query ──
    sender_ids = list({m.sender_id for m in msgs})
    senders = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()}

    # ── Batch load all read receipts + reader names in one query ──
    msg_ids = [m.id for m in msgs]
    reads_raw = (
        db.query(MessageRead.message_id, User.full_name)
        .join(User, User.id == MessageRead.user_id)
        .filter(MessageRead.message_id.in_(msg_ids))
        .all()
    )
    # Group by message_id
    reads_map = {}
    for mid, name in reads_raw:
        reads_map.setdefault(mid, []).append(name)

    reactions_map = get_reaction_summaries(db, msg_ids, current_user.id)

    # ── Online status: single query ──
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    online_user_ids = set(
        uid for (uid,) in db.query(User.id)
        .filter(User.id.in_(sender_ids), User.last_seen >= one_min_ago)
        .all()
    )
    online_user_ids.add(current_user.id)

    result = []
    for msg in msgs:
        sender = senders.get(msg.sender_id)
        read_by = reads_map.get(msg.id, [])
        result.append({
            "id": msg.id,
            "content": msg.content,
            "channel": channel,
            "message_type": msg.message_type.value if msg.message_type else "text",
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
            "author_name": sender.full_name if sender else "Unknown",
            "author_avatar_url": sender.avatar_url if sender else None,
            "author_badge": sender.badge if sender else "Member",
            "sender_is_admin": sender.is_admin if sender else False,
            "author_id": msg.sender_id,
            "read_count": len(read_by),
            "read_by": read_by,
            "is_online": msg.sender_id in online_user_ids,
            "reactions_summary": reactions_map.get(msg.id, []),
        })
    return result


# ─── POST /chat/messages — simple flat endpoint ─────────────
@router.post("/messages", status_code=201)
async def post_message_simple(
    data: SimpleMsgCreate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    ch = db.query(Channel).filter(Channel.name == data.channel).first()
    if not ch:
        # This used to parse "dm_{u1}_{u2}" out of the posted channel name and
        # create the channel plus both memberships for two arbitrary user ids,
        # then post into it — a message injected into a private conversation
        # between two people the sender had never met. It also auto-created any
        # group channel that was named.
        #
        # Creating a DM is POST /chat/dm, which binds the caller as one of the
        # two participants; creating a channel is an admin action. Posting
        # creates nothing.
        raise HTTPException(status_code=404, detail="Channel not found")

    # Group channels stay open — auto_join keeps the historical behaviour of a
    # first post joining you. A DM does not: membership is a precondition there,
    # never something the request grants itself.
    ensure_channel_access(db, ch.id, current_user, auto_join=True)

    # Determine message type
    msg_type = MessageType.TEXT
    if data.message_type == "image":
        msg_type = MessageType.IMAGE
    elif data.message_type == "voice":
        msg_type = MessageType.VOICE
    elif data.message_type == "file":
        msg_type = MessageType.FILE

    # Same rule as the socket path: the attachment is resolved against the
    # uploads tree, never taken from the request. See services/attachments.py.
    try:
        att_url, att_name, att_size = resolve_attachment(db, data.file_url, data.file_name)
    except InvalidAttachment as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    content = (data.content or "")[:MAX_MESSAGE_CHARS]
    if not content and not att_url:
        raise HTTPException(status_code=422, detail="Message is empty")

    msg = Message(
        channel_id=ch.id,
        sender_id=current_user.id,
        content=content,
        message_type=msg_type,
        file_url=att_url,
        file_name=att_name,
        file_size=att_size,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    from app.services.ws_manager import manager
    
    notified_ids = process_admin_mentions(db, current_user, data.content)
    for aid in notified_ids:
        await manager.send_personal(aid, {
            "event": "new_notification",
            "data": {
                "title": "New Mention in Chat",
                "body": f"{current_user.full_name} mentioned you in the community chat."
            }
        })

    result = {
        "id": msg.id,
        "content": msg.content,
        "channel": data.channel,
        "message_type": msg_type.value,
        "file_url": msg.file_url,
        "file_name": msg.file_name,
        "file_size": msg.file_size,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "author_name": current_user.full_name,
        "author_avatar_url": current_user.avatar_url,
        "author_badge": current_user.badge or "Member",
        "sender_is_admin": current_user.is_admin,
        "author_id": current_user.id,
        "read_count": 0,
        "read_by": [],
        "reactions_summary": [],
    }

    # Broadcast to all channel members so they receive it instantly without refreshing
    broadcast_data = {
        "event": "new_message",
        "data": {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "channel": data.channel,
            "sender_id": msg.sender_id,
            "sender_name": current_user.full_name,
            "sender_avatar": current_user.avatar_url,
            "sender_is_admin": current_user.is_admin,
            "content": msg.content,
            "message_type": msg_type.value,
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "reply_to_id": getattr(msg, 'reply_to_id', None),
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "author_id": current_user.id,
            "reactions_summary": [],
        }
    }
    await manager.broadcast_to_channel(msg.channel_id, broadcast_data)

    # 🔔 For DM channels: notify the recipient with a personal notification event
    # Channel name format is "dm_{user1_id}_{user2_id}"
    if ch.channel_type == ChannelType.DM:
        parts = ch.name.split("_")
        if len(parts) == 3:
            try:
                u1, u2 = int(parts[1]), int(parts[2])
                recipient_id = u2 if u1 == current_user.id else u1
                if recipient_id != current_user.id:
                    preview = (data.content or "")[:60]
                    if not preview:
                        preview = "📎 Sent a file"
                    await manager.send_personal(recipient_id, {
                        "event": "new_notification",
                        "data": {
                            "title": f"💬 {current_user.full_name}",
                            "body": preview,
                        }
                    })
            except (ValueError, IndexError):
                pass  # malformed channel name — skip notification silently

    return result


# ─── DELETE /chat/messages/{message_id} — delete own message ─
@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if msg.sender_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    
    msg.is_deleted = True
    msg.content = None
    msg.file_url = None
    channel_id = msg.channel_id
    db.commit()
    
    from app.services.ws_manager import manager
    await manager.broadcast_to_channel(channel_id, {
        "event": "message_deleted",
        "data": {
            "message_id": message_id,
            "channel_id": channel_id
        }
    })
    
    return {"message": "Message deleted"}


# ─── PUT /chat/messages/{message_id} — edit own message ──────
class EditMessageRequest(BaseModel):
    content: str


@router.put("/messages/{message_id}")
async def edit_message(
    message_id: int,
    data: EditMessageRequest,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Edit the text of one's own message. Reactions and read receipts live in
    separate tables and are intentionally left untouched, so an edit preserves
    both. Only the original sender may edit (admins cannot edit others')."""
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")

    # Only text messages are editable (image/voice/file bodies aren't text-editable here)
    if msg.message_type and msg.message_type != MessageType.TEXT:
        raise HTTPException(status_code=400, detail="Only text messages can be edited")

    new_content = (data.content or "").strip()
    if not new_content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    msg.content = new_content
    msg.edited_at = datetime.utcnow()
    channel_id = msg.channel_id
    db.commit()
    db.refresh(msg)

    from app.services.ws_manager import manager
    await manager.broadcast_to_channel(channel_id, {
        "event": "message_edited",
        "data": {
            "message_id": msg.id,
            "channel_id": channel_id,
            "content": msg.content,
            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        }
    })

    return {
        "id": msg.id,
        "content": msg.content,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
    }


class MarkReadRequest(BaseModel):
    message_ids: List[int]

@router.post("/mark-read")
async def mark_read(
    data: MarkReadRequest,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if not data.message_ids:
        return {"ok": True}

    # Only process messages the user didn't send themselves
    msgs = db.query(Message).filter(
        Message.id.in_(data.message_ids),
        Message.sender_id != current_user.id
    ).all()

    for msg in msgs:
        # Check if already read using the constraint logic or a query
        # Since we added UNIQUE constraint, we can just attempt insert
        # or do a query check to be safe
        existing = db.query(MessageRead).filter(
            MessageRead.message_id == msg.id,
            MessageRead.user_id == current_user.id
        ).first()
        if not existing:
            db.add(MessageRead(message_id=msg.id, user_id=current_user.id))
            msg.read_count = (msg.read_count or 0) + 1
            
    db.commit()

    # Broadcast read update to the affected channels
    channels_affected = list(set([msg.channel_id for msg in msgs]))
    for ch_id in channels_affected:
        await manager.broadcast_to_channel(ch_id, {
            "event": "message_read",
            "data": {"channel_id": ch_id, "user_id": current_user.id}
        })

    return {"ok": True}


# ─── GET /chat/online-count ─────────────────────────────────
@router.get("/online-count")
def get_online_count():
    """Return the number of users currently connected via WebSocket.
    Uses in-memory WS manager — zero DB queries — to avoid pool pressure
    from the high polling frequency on this endpoint."""
    return {"online_count": max(manager.get_online_count(), 1)}


# ─── GET /chat/admins ───────────────────────────────────────
@router.get("/admins")
def get_chat_admins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_member),
):
    admins = db.query(User).filter(User.is_admin == True, User.is_active == True).all()
    return [{"id": a.id, "full_name": a.full_name, "avatar_url": a.avatar_url} for a in admins]


# ─── Channels ────────────────────────────────────────────────

@router.get("/channels", response_model=List[ChannelOut])
def list_channels(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Only expose group channels plus the user's own DM channels — DM names
    # and last messages of other members must not leak to everyone.
    my_channel_ids = {
        cid for (cid,) in db.query(ChatMember.channel_id)
        .filter(ChatMember.user_id == current_user.id).all()
    }
    channels = [
        ch for ch in db.query(Channel).order_by(Channel.created_at).all()
        if ch.channel_type != ChannelType.DM or ch.id in my_channel_ids
    ]

    # Aggregate lookups — constant query count (was 4 queries per channel,
    # ~2300 total with 575 DM channels; took ~1.8s per request)
    member_counts = dict(
        db.query(ChatMember.channel_id, func.count(ChatMember.user_id))
        .group_by(ChatMember.channel_id).all()
    )
    last_msgs = {
        row.channel_id: row for row in db.execute(sqltext(
            "SELECT DISTINCT ON (channel_id) channel_id, content, created_at "
            "FROM messages WHERE is_deleted = false "
            "ORDER BY channel_id, created_at DESC"
        ))
    }
    unread_counts = dict(db.execute(sqltext(
        "SELECT m.channel_id, COUNT(*) FROM messages m "
        "JOIN chat_members cm ON cm.channel_id = m.channel_id AND cm.user_id = :uid "
        "WHERE m.is_deleted = false AND m.sender_id != :uid "
        "AND (cm.last_read_at IS NULL OR m.created_at > cm.last_read_at) "
        "GROUP BY m.channel_id"
    ), {"uid": current_user.id}).fetchall())

    return [
        ChannelOut(
            id=ch.id,
            name=ch.name,
            channel_type=ch.channel_type,
            description=ch.description,
            created_at=ch.created_at,
            member_count=member_counts.get(ch.id, 0),
            unread_count=unread_counts.get(ch.id, 0),
            last_message=last_msgs[ch.id].content if ch.id in last_msgs else None,
            last_message_at=last_msgs[ch.id].created_at if ch.id in last_msgs else None,
        )
        for ch in channels
    ]


@router.post("/channels", response_model=ChannelOut, status_code=201)
def create_channel(
    data: ChannelCreate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create channels")

    channel = Channel(
        name=data.name,
        channel_type=data.channel_type,
        description=data.description,
        created_by=current_user.id,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Add creator as admin member
    member = ChatMember(
        channel_id=channel.id,
        user_id=current_user.id,
        role=MemberRole.ADMIN,
    )
    db.add(member)
    db.commit()
    manager.subscribe(current_user.id, [channel.id])

    return ChannelOut(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        description=channel.description,
        created_at=channel.created_at,
        member_count=1,
        unread_count=0,
    )


# ─── Join Channel ────────────────────────────────────────────

@router.post("/channels/{channel_id}/join")
def join_channel(
    channel_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    existing = db.query(ChatMember).filter(
        ChatMember.channel_id == channel_id,
        ChatMember.user_id == current_user.id,
    ).first()

    if existing:
        return {"message": "Already a member"}

    member = ChatMember(
        channel_id=channel_id,
        user_id=current_user.id,
        role=MemberRole.MEMBER,
    )
    db.add(member)
    db.commit()
    manager.subscribe(current_user.id, [channel_id])
    return {"message": "Joined channel"}


# ─── Messages ────────────────────────────────────────────────

@router.get("/channels/{channel_id}/messages", response_model=List[MessageOut])
def list_messages(
    channel_id: int,
    before: int = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Open community channels auto-join on first read; a DM requires that the
    # caller already be one of its two participants. See ensure_channel_access.
    ensure_channel_access(db, channel_id, current_user, auto_join=True)

    q = db.query(Message).filter(Message.channel_id == channel_id, Message.is_deleted == False)

    if before:
        q = q.filter(Message.id < before)

    messages = q.order_by(desc(Message.created_at)).limit(limit).all()
    messages.reverse()  # Return in chronological order
    reactions_map = get_reaction_summaries(db, [msg.id for msg in messages], current_user.id)

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        result.append(MessageOut(
            id=msg.id,
            channel_id=msg.channel_id,
            sender_id=msg.sender_id,
            content=msg.content,
            message_type=msg.message_type,
            file_url=msg.file_url,
            file_name=msg.file_name,
            file_size=msg.file_size,
            reply_to_id=msg.reply_to_id,
            read_count=msg.read_count or 0,
            created_at=msg.created_at,
            sender_name=sender.full_name if sender else "Unknown",
            sender_avatar=sender.avatar_url if sender else None,
            sender_badge=sender.badge if sender else "Member",
            sender_is_admin=sender.is_admin if sender else False,
            reactions_summary=reactions_map.get(msg.id, []),
        ))

    return result


@router.post("/channels/{channel_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    channel_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Posting into a DM you are not part of was possible until this check
    # existed — the message landed in the conversation and broadcast to both
    # real participants.
    ensure_channel_access(db, channel_id, current_user, auto_join=True)

    msg = Message(
        channel_id=channel_id,
        sender_id=current_user.id,
        content=data.content,
        message_type=data.message_type,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size=data.file_size,
        reply_to_id=data.reply_to_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    process_admin_mentions(db, current_user, data.content)

    return MessageOut(
        id=msg.id,
        channel_id=msg.channel_id,
        sender_id=msg.sender_id,
        content=msg.content,
        message_type=msg.message_type,
        file_url=msg.file_url,
        file_name=msg.file_name,
        file_size=msg.file_size,
        reply_to_id=msg.reply_to_id,
        read_count=0,
        created_at=msg.created_at,
        sender_name=current_user.full_name,
        sender_avatar=current_user.avatar_url,
        sender_badge=current_user.badge or "Member",
        sender_is_admin=current_user.is_admin,
        reactions_summary=[],
    )


# ─── Mark Read ───────────────────────────────────────────────

@router.put("/channels/{channel_id}/read")
def mark_channel_read(
    channel_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    membership = db.query(ChatMember).filter(
        ChatMember.channel_id == channel_id,
        ChatMember.user_id == current_user.id,
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Not a member")

    membership.last_read_at = datetime.utcnow()
    db.commit()
    return {"message": "Marked as read"}


# ─── DM full-channel read (clears the DM unread badge) ───────

@router.put("/dm/read")
async def mark_dm_channel_read(
    channel: str,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Mark EVERY message in a DM channel as read for the current user.

    DM unread counts are per-message (MessageRead rows). The on-screen
    IntersectionObserver only marks messages that become visible, so opening
    a conversation left older messages unread and the badge never cleared.
    This bulk-marks the whole channel when the user opens it.
    """
    ch = db.query(Channel).filter(
        Channel.name == channel,
        Channel.channel_type == ChannelType.DM,
    ).first()
    if not ch:
        return {"ok": True, "marked": 0}

    # Only participants may mark the channel read
    is_member = db.query(ChatMember).filter(
        ChatMember.channel_id == ch.id,
        ChatMember.user_id == current_user.id,
    ).first()
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this channel")

    already_read = set(
        mid for (mid,) in db.query(MessageRead.message_id)
        .join(Message, Message.id == MessageRead.message_id)
        .filter(MessageRead.user_id == current_user.id, Message.channel_id == ch.id)
        .all()
    )
    unread_q = db.query(Message).filter(
        Message.channel_id == ch.id,
        Message.sender_id != current_user.id,
        Message.is_deleted == False,
    )
    if already_read:
        unread_q = unread_q.filter(~Message.id.in_(already_read))
    unread = unread_q.all()

    for msg in unread:
        db.add(MessageRead(message_id=msg.id, user_id=current_user.id))
        msg.read_count = (msg.read_count or 0) + 1
    db.commit()

    if unread:
        await manager.broadcast_to_channel(ch.id, {
            "event": "message_read",
            "data": {"channel_id": ch.id, "user_id": current_user.id}
        })

    return {"ok": True, "marked": len(unread)}


# ─── Community Chat Unread (sidebar badge) ───────────────────

class CommunityReadRequest(BaseModel):
    channel: str = "general"


@router.get("/community/unread")
def get_community_unread(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Total unread messages across community (group) channels — for the sidebar badge."""
    # "start-here" is a legacy chat channel; the UI now renders Start Here as a
    # static content page, so its old messages can never be read — exclude it.
    group_channels = (
        db.query(Channel)
        .filter(
            Channel.channel_type == ChannelType.GROUP,
            Channel.name.notin_(["start-here", "start_here"]),
        )
        .all()
    )
    memberships = {
        m.channel_id: m
        for m in db.query(ChatMember).filter(ChatMember.user_id == current_user.id).all()
    }

    total = 0
    per_channel = {}
    for ch in group_channels:
        m = memberships.get(ch.id)
        since = (m.last_read_at or m.joined_at) if m else current_user.created_at
        q = db.query(func.count(Message.id)).filter(
            Message.channel_id == ch.id,
            Message.sender_id != current_user.id,
            Message.is_deleted == False,
        )
        if since:
            q = q.filter(Message.created_at > since)
        count = q.scalar() or 0
        total += count
        if count:
            per_channel[ch.name] = per_channel.get(ch.name, 0) + count

    # ── Community post channels (forum categories on the chat page) ──
    post_slugs = [
        s for (s,) in db.query(Post.category_slug)
        .filter(Post.category_slug.isnot(None)).distinct().all()
    ]
    post_reads = {
        r.channel: r
        for r in db.query(PostChannelRead).filter(PostChannelRead.user_id == current_user.id).all()
    }
    for slug in post_slugs:
        r = post_reads.get(slug)
        since = (r.last_read_at if r else None) or current_user.created_at
        q = db.query(func.count(Post.id)).filter(
            Post.category_slug == slug,
            Post.user_id != current_user.id,
        )
        if since:
            q = q.filter(Post.created_at > since)
        count = q.scalar() or 0
        total += count
        if count:
            per_channel[slug] = per_channel.get(slug, 0) + count

    return {"unread_count": total, "channels": per_channel}


@router.put("/community/read")
def mark_community_channel_read(
    data: CommunityReadRequest,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Mark a community channel as read by name — chat (group) channel or post channel."""
    ch = db.query(Channel).filter(
        Channel.name == data.channel,
        Channel.channel_type == ChannelType.GROUP,
    ).first()
    if ch:
        membership = db.query(ChatMember).filter(
            ChatMember.channel_id == ch.id,
            ChatMember.user_id == current_user.id,
        ).first()
        if not membership:
            membership = ChatMember(channel_id=ch.id, user_id=current_user.id)
            db.add(membership)
        membership.last_read_at = datetime.utcnow()
        db.commit()
        return {"ok": True}

    # Post channel (forum category) — only track slugs that actually have posts
    has_posts = db.query(Post.id).filter(Post.category_slug == data.channel).first()
    if has_posts:
        read_state = db.query(PostChannelRead).filter(
            PostChannelRead.user_id == current_user.id,
            PostChannelRead.channel == data.channel,
        ).first()
        if not read_state:
            read_state = PostChannelRead(user_id=current_user.id, channel=data.channel)
            db.add(read_state)
        read_state.last_read_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


# ─── Channel Members ────────────────────────────────────────

@router.get("/channels/{channel_id}/members")
def list_channel_members(
    channel_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    # Was open to the whole internet: names and avatars of every member, and —
    # because DM channels have rosters too — who is talking to whom privately.
    ensure_channel_access(db, channel_id, current_user)

    members = (
        db.query(ChatMember)
        .filter(ChatMember.channel_id == channel_id)
        .all()
    )
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user and user.is_active:
            result.append({
                "user_id": m.user_id,
                "role": m.role.value,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
            })
    return result


# ─── File Upload ─────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member),
):
    try:
        result = await save_upload(file, subfolder="chat")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── DM (Direct Messages) ────────────────────────────────────

class DMRequest(BaseModel):
    target_user_id: int

@router.post("/dm")
def get_or_create_dm(
    data: DMRequest,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Get or create a DM channel between current user and target user."""
    if data.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself")

    target = db.query(User).filter(User.id == data.target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Deterministic channel name: dm_{lower_id}_{higher_id}
    ids = sorted([current_user.id, data.target_user_id])
    dm_name = f"dm_{ids[0]}_{ids[1]}"

    # Check if DM channel already exists
    ch = db.query(Channel).filter(
        Channel.name == dm_name,
        Channel.channel_type == ChannelType.DM
    ).first()

    if not ch:
        ch = Channel(name=dm_name, channel_type=ChannelType.DM)
        db.add(ch)
        db.commit()
        db.refresh(ch)

        # Add both users as members
        db.add(ChatMember(channel_id=ch.id, user_id=current_user.id, role=MemberRole.MEMBER))
        db.add(ChatMember(channel_id=ch.id, user_id=data.target_user_id, role=MemberRole.MEMBER))
        db.commit()
        manager.subscribe(current_user.id, [ch.id])
        manager.subscribe(data.target_user_id, [ch.id])

    return {
        "channel_name": dm_name,
        "channel_id": ch.id,
        "target_user": {
            "id": target.id,
            "full_name": target.full_name,
            "avatar_url": target.avatar_url,
            "badge": target.badge or "Member",
        }
    }


@router.get("/dm/list")
def list_dm_conversations(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """List all DM channels for the current user."""
    dm_channels = (
        db.query(Channel)
        .join(ChatMember, ChatMember.channel_id == Channel.id)
        .filter(
            ChatMember.user_id == current_user.id,
            Channel.channel_type == ChannelType.DM
        )
        .all()
    )

    ch_ids = [ch.id for ch in dm_channels] if dm_channels else []

    # ── Fetch all Admins (to pin) ──
    admins = db.query(User).filter(User.is_admin == True, User.is_active == True, User.id != current_user.id).all()
    admin_ids = {a.id for a in admins}

    ch_ids = [ch.id for ch in dm_channels]

    # ── Batch: get all other members in these DM channels ──
    other_members = (
        db.query(ChatMember)
        .filter(ChatMember.channel_id.in_(ch_ids), ChatMember.user_id != current_user.id)
        .all()
    ) if ch_ids else []
    
    ch_to_other_uid = {m.channel_id: m.user_id for m in other_members}
    other_user_ids = list(set(ch_to_other_uid.values()))

    # ── Batch: load all other users ──
    all_needed_user_ids = list(set(other_user_ids) | admin_ids)
    other_users = {u.id: u for u in db.query(User).filter(User.id.in_(all_needed_user_ids)).all()}

    # ── Batch: get last message per channel using a subquery ──
    if ch_ids:
        from sqlalchemy import and_
        last_msg_subq = (
            db.query(Message.channel_id, func.max(Message.id).label("max_id"))
            .filter(Message.channel_id.in_(ch_ids), Message.is_deleted == False)
            .group_by(Message.channel_id)
            .subquery()
        )
        last_msgs_raw = (
            db.query(Message)
            .join(last_msg_subq, and_(Message.id == last_msg_subq.c.max_id))
            .all()
        )
        last_msgs = {m.channel_id: m for m in last_msgs_raw}

        # ── Batch: get my read message IDs in these channels ──
        my_read_ids = set(
            mid for (mid,) in db.query(MessageRead.message_id)
            .join(Message, Message.id == MessageRead.message_id)
            .filter(MessageRead.user_id == current_user.id, Message.channel_id.in_(ch_ids))
            .all()
        )

        # ── Batch: count unread per channel (messages from others I haven't read) ──
        unread_msgs = (
            db.query(Message.channel_id, Message.id)
            .filter(
                Message.channel_id.in_(ch_ids),
                Message.sender_id != current_user.id,
                Message.is_deleted == False,
            )
            .all()
        )
        unread_counts = {}
        for ch_id, msg_id in unread_msgs:
            if msg_id not in my_read_ids:
                unread_counts[ch_id] = unread_counts.get(ch_id, 0) + 1
    else:
        last_msgs = {}
        unread_counts = {}

    one_min_ago = datetime.utcnow() - timedelta(seconds=60)

    result = []
    processed_user_ids = set()

    for ch in dm_channels:
        other_uid = ch_to_other_uid.get(ch.id)
        if not other_uid:
            continue
        other_user = other_users.get(other_uid)
        if not other_user:
            continue

        is_online = other_user.last_seen and other_user.last_seen >= one_min_ago
        last_msg = last_msgs.get(ch.id)
        
        is_pinned = other_uid in admin_ids
        processed_user_ids.add(other_uid)

        result.append({
            "channel_name": ch.name,
            "channel_id": ch.id,
            "is_pinned": is_pinned,
            "user": {
                "id": other_user.id,
                "full_name": other_user.full_name,
                "avatar_url": other_user.avatar_url,
                "badge": other_user.badge or "Member",
                "is_online": is_online,
                "is_admin": other_user.is_admin,
            },
            "last_message": last_msg.content if last_msg else None,
            "last_message_type": last_msg.message_type.value if last_msg and last_msg.message_type else "text",
            "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            "unread_count": unread_counts.get(ch.id, 0),
        })

    # Add admins who don't have a DM channel yet
    for admin_id in admin_ids:
        if admin_id not in processed_user_ids:
            admin_user = other_users.get(admin_id)
            if not admin_user:
                continue
            is_online = admin_user.last_seen and admin_user.last_seen >= one_min_ago
            
            # Deterministic channel name
            ids = sorted([current_user.id, admin_id])
            dm_name = f"dm_{ids[0]}_{ids[1]}"
            
            result.append({
                "channel_name": dm_name,
                "channel_id": None,
                "is_pinned": True,
                "user": {
                    "id": admin_user.id,
                    "full_name": admin_user.full_name,
                    "avatar_url": admin_user.avatar_url,
                    "badge": admin_user.badge or "Admin",
                    "is_online": is_online,
                    "is_admin": True,
                },
                "last_message": "Start chatting...",
                "last_message_type": "text",
                "last_message_at": None,
                "unread_count": 0,
            })

    result.sort(key=lambda x: (x.get("is_pinned", False), x["last_message_at"] or ""), reverse=True)
    return result


# ─── Members List (for New DM Modal) ────────────────────────

@router.get("/members")
def list_active_members(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """List all active/verified members for the new message search modal."""
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    users = (
        db.query(User)
        .filter(User.id != current_user.id, User.is_verified == True, User.is_active == True)
        .order_by(User.full_name)
        .all()
    )
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "is_online": u.last_seen is not None and u.last_seen >= one_min_ago,
            "badge": u.badge or "Member",
            "is_admin": u.is_admin,
            "custom_title": u.custom_title or "",
        }
        for u in users
    ]


# ─── Avatar Upload ───────────────────────────────────────────

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    from app.services.file_service import save_avatar
    try:
        url = await save_avatar(file)
        current_user.avatar_url = url
        db.commit()
        return {"avatar_url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
