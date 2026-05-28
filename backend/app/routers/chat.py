"""
Chat Router — Channels, Messages (REST), File Uploads, Read Receipts, Delete
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.services.ws_manager import manager
from app.models import User, Channel, ChatMember, Message, MessageRead, MemberRole, ChannelType, MessageType
from app.schemas import ChannelCreate, ChannelOut, MessageCreate, MessageOut, ChatMemberOut
from app.routers.users import get_current_user, get_current_active_member
from app.services.file_service import save_upload
from pydantic import BaseModel

import json
import os
from pathlib import Path as FilePath

router = APIRouter(prefix="/chat", tags=["Chat"])

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
            "author_name": sender.full_name if sender else "Unknown",
            "author_avatar_url": sender.avatar_url if sender else None,
            "author_badge": sender.badge if sender else "Member",
            "author_id": msg.sender_id,
            "read_count": len(read_by),
            "read_by": read_by,
            "is_online": msg.sender_id in online_user_ids,
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
        # Auto-create channel
        ch = Channel(name=data.channel, channel_type=ChannelType.GROUP)
        db.add(ch)
        db.commit()
        db.refresh(ch)

    # Determine message type
    msg_type = MessageType.TEXT
    if data.message_type == "image":
        msg_type = MessageType.IMAGE
    elif data.message_type == "voice":
        msg_type = MessageType.VOICE
    elif data.message_type == "file":
        msg_type = MessageType.FILE

    msg = Message(
        channel_id=ch.id,
        sender_id=current_user.id,
        content=data.content,
        message_type=msg_type,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size=data.file_size,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

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
        "author_id": current_user.id,
        "read_count": 0,
        "read_by": [],
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
            "content": msg.content,
            "message_type": msg_type.value,
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "reply_to_id": getattr(msg, 'reply_to_id', None),
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "author_id": current_user.id,
        }
    }
    await manager.broadcast_to_channel(msg.channel_id, broadcast_data)

    return result


# ─── DELETE /chat/messages/{message_id} — delete own message ─
@router.delete("/messages/{message_id}")
def delete_message(
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
    db.commit()
    
    return {"message": "Message deleted"}


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
def get_online_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_member),
):
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    count = (
        db.query(func.count(User.id))
        .filter(User.last_seen >= one_min_ago)
        .scalar()
    )
    # Current user is always counted as online
    return {"online_count": max(count or 0, 1)}


# ─── Channels ────────────────────────────────────────────────

@router.get("/channels", response_model=List[ChannelOut])
def list_channels(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    channels = db.query(Channel).order_by(Channel.created_at).all()
    result = []

    for ch in channels:
        # Get member count
        member_count = db.query(ChatMember).filter(ChatMember.channel_id == ch.id).count()

        # Get last message
        last_msg = (
            db.query(Message)
            .filter(Message.channel_id == ch.id, Message.is_deleted == False)
            .order_by(desc(Message.created_at))
            .first()
        )

        # Get unread count for this user
        membership = (
            db.query(ChatMember)
            .filter(ChatMember.channel_id == ch.id, ChatMember.user_id == current_user.id)
            .first()
        )
        unread = 0
        if membership and membership.last_read_at:
            unread = (
                db.query(Message)
                .filter(
                    Message.channel_id == ch.id,
                    Message.created_at > membership.last_read_at,
                    Message.sender_id != current_user.id,
                    Message.is_deleted == False,
                )
                .count()
            )
        elif membership:
            unread = db.query(Message).filter(
                Message.channel_id == ch.id,
                Message.sender_id != current_user.id,
                Message.is_deleted == False,
            ).count()

        result.append(ChannelOut(
            id=ch.id,
            name=ch.name,
            channel_type=ch.channel_type,
            description=ch.description,
            created_at=ch.created_at,
            member_count=member_count,
            unread_count=unread,
            last_message=last_msg.content if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else None,
        ))

    return result


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
    # Auto-join user to channel if not a member
    membership = db.query(ChatMember).filter(
        ChatMember.channel_id == channel_id,
        ChatMember.user_id == current_user.id,
    ).first()
    if not membership:
        member = ChatMember(
            channel_id=channel_id,
            user_id=current_user.id,
            role=MemberRole.MEMBER,
        )
        db.add(member)
        db.commit()
        membership = member

    q = db.query(Message).filter(Message.channel_id == channel_id, Message.is_deleted == False)

    if before:
        q = q.filter(Message.id < before)

    messages = q.order_by(desc(Message.created_at)).limit(limit).all()
    messages.reverse()  # Return in chronological order

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
        ))

    return result


@router.post("/channels/{channel_id}/messages", response_model=MessageOut, status_code=201)
def send_message(
    channel_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

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


# ─── Channel Members ────────────────────────────────────────

@router.get("/channels/{channel_id}/members")
def list_channel_members(
    channel_id: int,
    db: Session = Depends(get_db),
):
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

    if not dm_channels:
        return []

    ch_ids = [ch.id for ch in dm_channels]

    # ── Batch: get all other members in these DM channels ──
    other_members = (
        db.query(ChatMember)
        .filter(ChatMember.channel_id.in_(ch_ids), ChatMember.user_id != current_user.id)
        .all()
    )
    ch_to_other_uid = {m.channel_id: m.user_id for m in other_members}
    other_user_ids = list(set(ch_to_other_uid.values()))

    # ── Batch: load all other users ──
    other_users = {u.id: u for u in db.query(User).filter(User.id.in_(other_user_ids)).all()}

    # ── Batch: get last message per channel using a subquery ──
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

    one_min_ago = datetime.utcnow() - timedelta(seconds=60)

    result = []
    for ch in dm_channels:
        other_uid = ch_to_other_uid.get(ch.id)
        if not other_uid:
            continue
        other_user = other_users.get(other_uid)
        if not other_user:
            continue

        is_online = other_user.last_seen and other_user.last_seen >= one_min_ago
        last_msg = last_msgs.get(ch.id)

        result.append({
            "channel_name": ch.name,
            "channel_id": ch.id,
            "user": {
                "id": other_user.id,
                "full_name": other_user.full_name,
                "avatar_url": other_user.avatar_url,
                "badge": other_user.badge or "Member",
                "is_online": is_online,
            },
            "last_message": last_msg.content if last_msg else None,
            "last_message_type": last_msg.message_type.value if last_msg and last_msg.message_type else "text",
            "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            "unread_count": unread_counts.get(ch.id, 0),
        })

    result.sort(key=lambda x: x["last_message_at"] or "", reverse=True)
    return result


# ─── Members List (for New DM Modal) ────────────────────────

@router.get("/members")
def list_active_members(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """List all active/verified members for the new message search modal."""
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
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
            "is_online": u.last_seen is not None and u.last_seen >= five_min_ago,
            "badge": u.badge or "Member",
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
