"""
WebSocket Router — Real-time chat messaging
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.database import SessionLocal
from app.models import User, Message, ChatMember, Channel, MessageType
from app.services.ws_manager import manager
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
                # Auto-create membership
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

        # Listen for messages
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action")

            if action == "send_message":
                await handle_send_message(user, data, db)

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
            manager.disconnect(user.id)
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
