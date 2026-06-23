"""
WebSocket Router — Real-time chat messaging
"""
import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.database import SessionLocal
from app.models import User, Message, ChatMember, Channel, MessageType
from app.services.ws_manager import manager
from app.services.chat_reactions import get_reaction_summary, set_message_reaction
from app.services.mentions_service import process_admin_mentions
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

router = APIRouter(tags=["WebSocket"])


def get_user_from_token(token: str, db: Session) -> User:
    """Validate JWT token and return user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    db = SessionLocal()

    try:
        # Authenticate
        user = get_user_from_token(token, db)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return

        if not user.is_active:
            await websocket.close(code=4003, reason="Account is not active")
            return

        # Connect
        await manager.connect(websocket, user.id)

        # Subscribe user to all their channels
        memberships = db.query(ChatMember).filter(ChatMember.user_id == user.id).all()
        channel_ids = [m.channel_id for m in memberships]

        # Also subscribe to all group channels (auto-join behavior)
        all_group_channels = db.query(Channel).filter(Channel.channel_type == "group").all()
        for ch in all_group_channels:
            if ch.id not in channel_ids:
                channel_ids.append(ch.id)
                # Auto-create membership only if not already a member
                already_member = db.query(ChatMember).filter(
                    ChatMember.channel_id == ch.id,
                    ChatMember.user_id == user.id
                ).first()
                if not already_member:
                    new_member = ChatMember(channel_id=ch.id, user_id=user.id)
                    db.add(new_member)
        db.commit()

        manager.subscribe(user.id, channel_ids)

        # Send initial connection confirmation
        await manager.send_personal(user.id, {
            "event": "connected",
            "data": {
                "user_id": user.id,
                "user_name": user.full_name,
                "channels": channel_ids,
                "online_count": manager.get_online_count(),
            }
        })

        # Broadcast online status
        for ch_id in channel_ids:
            await manager.broadcast_to_channel(ch_id, {
                "event": "user_online",
                "data": {"user_id": user.id, "user_name": user.full_name}
            }, exclude_user=user.id)

        # Listen for messages — with periodic re-validation every 30s
        last_check = asyncio.get_event_loop().time()
        CHECK_INTERVAL = 30  # seconds

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=CHECK_INTERVAL)
            except asyncio.TimeoutError:
                # Periodic check: re-validate user still exists and is active
                db.expire_all()  # refresh DB session
                fresh_user = db.query(User).filter(User.id == user.id).first()
                if not fresh_user or not fresh_user.is_active:
                    reason = "User deleted" if not fresh_user else "Account deactivated"
                    logger.info(f"WS kicking user {user.id}: {reason}")
                    await websocket.close(code=4003, reason=reason)
                    return
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action")
            event = data.get("event")

            if action == "send_message":
                await handle_send_message(user, data, db)

            elif event == "message_reaction":
                await handle_message_reaction(user, data.get("data") or {}, db)

            elif action == "typing":
                channel_id = data.get("channel_id")
                if channel_id:
                    await manager.broadcast_to_channel(channel_id, {
                        "event": "typing",
                        "data": {
                            "channel_id": channel_id,
                            "user_id": user.id,
                            "user_name": user.full_name,
                        }
                    }, exclude_user=user.id)

            elif action == "mark_read":
                channel_id = data.get("channel_id")
                if channel_id:
                    from datetime import datetime
                    membership = db.query(ChatMember).filter(
                        ChatMember.channel_id == channel_id,
                        ChatMember.user_id == user.id,
                    ).first()
                    if membership:
                        membership.last_read_at = datetime.utcnow()
                        db.commit()

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: user {user.id if user else '?'}")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        if user:
            manager.disconnect(websocket, user.id)
            # Broadcast offline status
            memberships = db.query(ChatMember).filter(ChatMember.user_id == user.id).all()
            for m in memberships:
                await manager.broadcast_to_channel(m.channel_id, {
                    "event": "user_offline",
                    "data": {"user_id": user.id, "user_name": user.full_name}
                })
        db.close()


async def handle_send_message(user: User, data: dict, db: Session):
    """Process and broadcast a new chat message."""
    channel_id = data.get("channel_id")
    content = data.get("content", "")
    message_type_str = data.get("message_type", "text")
    file_url = data.get("file_url")
    file_name = data.get("file_name")
    file_size = data.get("file_size")
    reply_to_id = data.get("reply_to_id")

    if not channel_id:
        return

    # Validate message type
    try:
        msg_type = MessageType(message_type_str)
    except ValueError:
        msg_type = MessageType.TEXT

    # Save to database
    msg = Message(
        channel_id=channel_id,
        sender_id=user.id,
        content=content,
        message_type=msg_type,
        file_url=file_url,
        file_name=file_name,
        file_size=file_size,
        reply_to_id=reply_to_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Process admin mentions
    notified_ids = process_admin_mentions(db, user, content)
    for aid in notified_ids:
        await manager.send_personal(aid, {
            "event": "new_notification",
            "data": {
                "title": "New Mention in Chat",
                "body": f"{user.full_name} mentioned you in the community chat."
            }
        })

    # Broadcast to all channel members
    broadcast_data = {
        "event": "new_message",
        "data": {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "sender_id": msg.sender_id,
            "sender_name": user.full_name,
            "sender_avatar": user.avatar_url,
            "content": msg.content,
            "message_type": msg.message_type.value,
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "reply_to_id": msg.reply_to_id,
            "created_at": msg.created_at.isoformat(),
        }
    }

    await manager.broadcast_to_channel(channel_id, broadcast_data)


async def handle_message_reaction(user: User, data: dict, db: Session):
    """Save/delete a reaction and broadcast personalized reaction summaries."""
    message_id = data.get("message_id")
    emoji = data.get("emoji")
    action = data.get("action")

    if not message_id or not emoji or action not in {"add", "remove"}:
        await manager.send_personal(user.id, {
            "event": "reaction_error",
            "data": {"message": "Invalid reaction payload"}
        })
        return

    try:
        message = set_message_reaction(
            db,
            message_id=int(message_id),
            user_id=user.id,
            emoji=emoji,
            action=action,
        )
    except (LookupError, PermissionError, ValueError) as exc:
        await manager.send_personal(user.id, {
            "event": "reaction_error",
            "data": {"message": str(exc)}
        })
        return

    subscribers = list(manager.channel_subscriptions.get(message.channel_id, set()))
    for subscriber_id in subscribers:
        await manager.send_personal(subscriber_id, {
            "event": "reaction_updated",
            "type": "reaction_updated",
            "data": {
                "message_id": message.id,
                "reactions_summary": get_reaction_summary(db, message.id, subscriber_id),
            }
        })
