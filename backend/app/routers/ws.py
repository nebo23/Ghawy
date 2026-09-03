"""
WebSocket Router — Real-time chat messaging
"""
import json
import logging
import time
from app.services.attachments import resolve_attachment, InvalidAttachment
import asyncio
from contextlib import contextmanager
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.database import SessionLocal
from app.models import User, Message, ChatMember, Channel, ChannelType, MessageType
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


@contextmanager
def db_session():
    """Short-lived DB session.

    A WebSocket connection lives for minutes/hours but is idle almost the whole
    time. Holding one `SessionLocal()` for the connection's lifetime pins a
    pooled DB connection (often stuck "idle in transaction" after a read), so a
    few dozen connected users exhaust the pool and every HTTP request starts
    failing with QueuePool timeout. Instead we open a session only for the brief
    moment we touch the DB and close it immediately, so an idle socket holds
    zero DB connections.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_from_token(token: str, db: Session) -> User:
    """Validate JWT token and return user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = None
    user_name = None
    channel_ids = []

    try:
        # 🔒 Accept first, then wait for auth message — keeps the token out of the URL/logs
        await websocket.accept()
        try:
            auth_msg_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            auth_msg = json.loads(auth_msg_raw)
        except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
            logger.warning("WS auth failed: no/invalid auth message — %s", e)
            await websocket.close(code=4001, reason="Auth required")
            return

        token = auth_msg.get("token") if isinstance(auth_msg, dict) else None
        if not token:
            await websocket.close(code=4001, reason="Token missing")
            return

        # Authenticate + initial channel setup — short-lived session, closed before we idle
        with db_session() as db:
            user = get_user_from_token(token, db)
            if not user:
                await websocket.close(code=4001, reason="Invalid token")
                return

            if not user.is_active:
                await websocket.close(code=4003, reason="Account is not active")
                return

            user_id = user.id
            user_name = user.full_name

            # Subscribe user to all their channels
            memberships = db.query(ChatMember).filter(ChatMember.user_id == user_id).all()
            channel_ids = [m.channel_id for m in memberships]

            # Also subscribe to all group channels (auto-join behavior)
            all_group_channels = db.query(Channel).filter(Channel.channel_type == "group").all()
            for ch in all_group_channels:
                if ch.id not in channel_ids:
                    # Reaching here already means there is no membership row:
                    # channel_ids is built from this user's memberships, loaded
                    # immediately above, and this branch only runs for a channel
                    # that is not in it. The per-channel "already_member" SELECT
                    # that used to sit here could therefore only ever return
                    # None — one wasted query per group channel on every socket
                    # connect, asking a question the list in hand had answered.
                    channel_ids.append(ch.id)
                    db.add(ChatMember(channel_id=ch.id, user_id=user_id))
            db.commit()

        # Connect (already accepted above, so skip the accept inside the manager)
        await manager.connect(websocket, user_id, accept=False)
        manager.subscribe(user_id, channel_ids)

        # Send initial connection confirmation
        await manager.send_personal(user_id, {
            "event": "connected",
            "data": {
                "user_id": user_id,
                "user_name": user_name,
                "channels": channel_ids,
                "online_count": manager.get_online_count(),
            }
        })

        # Presence is a global fact, not a per-channel one. This used to loop
        # over every channel the user belongs to, and because everyone is
        # auto-joined to every group channel that delivered the SAME event to
        # each recipient once per shared channel — roughly four copies each.
        # Every copy makes the receiving tab refetch the online count and the
        # whole DM list, so a single reconnect fanned out into a burst of
        # duplicate work on every open tab (13.7k /chat/dm/list calls in 30
        # minutes from 20 members, enough to sit on the rate limiter). One send
        # per connected user carries exactly the same information.
        await manager.broadcast_to_all({
            "event": "user_online",
            "data": {"user_id": user_id, "user_name": user_name}
        }, exclude_user=user_id)

        # Listen for messages — with periodic re-validation
        CHECK_INTERVAL = 55  # seconds — must be < nginx proxy_read_timeout (60s)

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=CHECK_INTERVAL)
            except asyncio.TimeoutError:
                # Periodic keepalive: re-validate user + ping to detect dead connections
                with db_session() as db:
                    fresh_user = db.query(User).filter(User.id == user_id).first()
                    still_active = bool(fresh_user and fresh_user.is_active)
                    kick_reason = None if still_active else (
                        "User deleted" if not fresh_user else "Account deactivated"
                    )
                if not still_active:
                    logger.info(f"WS kicking user {user_id}: {kick_reason}")
                    await websocket.close(code=4003, reason=kick_reason)
                    return
                # 🏓 Send ping — keeps connection alive through proxies and detects silent drops
                try:
                    await asyncio.wait_for(websocket.send_text('{"event":"ping"}'), timeout=5.0)
                except Exception:
                    # Connection is dead — exit so onclose fires and client reconnects
                    logger.info(f"WS ping failed for user {user_id}, treating as disconnect")
                    return
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action")
            event = data.get("event")

            if action == "send_message":
                await handle_send_message(user_id, data)

            elif event == "message_reaction":
                await handle_message_reaction(user_id, data.get("data") or {})

            elif action == "typing":
                channel_id = data.get("channel_id")
                # send_message checks the channel; these two did not, so a
                # stranger could type into someone else's DM — the participants
                # would see "X is typing…" in a conversation X is not part of.
                # All three socket actions go through the one check now.
                if channel_id and _has_channel_access(channel_id, user_id):
                    await manager.broadcast_to_channel(channel_id, {
                        "event": "typing",
                        "data": {
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "user_name": user_name,
                        }
                    }, exclude_user=user_id)

            elif action == "mark_read":
                channel_id = data.get("channel_id")
                if channel_id and _has_channel_access(channel_id, user_id):
                    from datetime import datetime
                    with db_session() as db:
                        membership = db.query(ChatMember).filter(
                            ChatMember.channel_id == channel_id,
                            ChatMember.user_id == user_id,
                        ).first()
                        if membership:
                            membership.last_read_at = datetime.utcnow()
                            db.commit()

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: user {user_id if user_id else '?'}")
    except RuntimeError as e:
        # Gracefully handle "Unexpected ASGI message 'websocket.close'"
        # This happens when a client drops the connection abruptly and
        # the server tries to close an already-closed socket — harmless.
        if "websocket.close" in str(e) or "already completed" in str(e):
            logger.debug(f"WS already closed for user {user_id}: {e}")
        else:
            logger.error(f"WS runtime error for user {user_id}: {e}")
    except Exception as e:
        logger.error(f"WS error for user {user_id}: {e}")
    finally:
        if user_id:
            manager.disconnect(websocket, user_id)
            # Broadcast offline status
            try:
                # Same de-duplication as the user_online broadcast above. This
                # also drops the membership lookup that used to run on every
                # single disconnect — presence needs no channel list, so the
                # teardown path no longer touches the DB at all.
                await manager.broadcast_to_all({
                    "event": "user_offline",
                    "data": {"user_id": user_id, "user_name": user_name}
                })
            except Exception as cleanup_err:
                logger.debug(f"WS cleanup error for user {user_id}: {cleanup_err}")


def _may_post_to_channel(db: Session, channel_id, user_id: int) -> bool:
    """May this user write into this channel?

    Community (group/announcement) channels are open to every active member and
    auto-join on first use — that is the product. A DM belongs to the two people
    /chat/dm put in it, so it needs an existing membership row and never grants
    one. Mirrors ensure_channel_access in routers/chat.py; the two must agree,
    or a rule enforced over HTTP is simply bypassed over the socket.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        return False

    membership = db.query(ChatMember).filter(
        ChatMember.channel_id == channel_id,
        ChatMember.user_id == user_id,
    ).first()

    if channel.channel_type == ChannelType.DM:
        return membership is not None

    if not membership:
        db.add(ChatMember(channel_id=channel_id, user_id=user_id))
        db.commit()
        manager.subscribe(user_id, [channel_id])
    return True


# A chat message is a paragraph, not a payload. Anything longer is either a
# paste accident or someone filling the table.
MAX_MESSAGE_CHARS = 4000

# Per-user send rate limit. There was none in the app layer at all: nginx's
# limit_req does not see socket frames, so one connection could write to the
# messages table as fast as it could serialize JSON. In-memory is the right
# scope here — the limit is per connection-holder and a worker restart handing
# someone a fresh allowance is not worth a round trip to the database.
SEND_RATE_LIMIT = 20          # messages …
SEND_RATE_WINDOW = 10.0       # … per this many seconds
_send_times: dict[int, list[float]] = {}


def _within_send_rate(user_id: int) -> bool:
    now = time.monotonic()
    times = [t for t in _send_times.get(user_id, []) if now - t < SEND_RATE_WINDOW]
    if len(times) >= SEND_RATE_LIMIT:
        _send_times[user_id] = times
        return False
    times.append(now)
    _send_times[user_id] = times
    return True


def _has_channel_access(channel_id, user_id: int) -> bool:
    """_may_post_to_channel with its own session, for the socket's inline actions."""
    try:
        with db_session() as db:
            return _may_post_to_channel(db, channel_id, user_id)
    except Exception:
        logger.warning("WS channel access check failed for user %s channel %s",
                       user_id, channel_id, exc_info=True)
        return False


async def handle_send_message(user_id: int, data: dict):
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

    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return

        # The channel_id arrives in a socket frame the client writes, and until
        # this check it was used verbatim — so a member could address a frame at
        # a DM channel between two other people and have it delivered to both.
        # The REST path enforces the same rule; see ensure_channel_access in
        # routers/chat.py.
        if not _may_post_to_channel(db, channel_id, user_id):
            logger.warning("WS user %s tried to post into channel %s without access",
                           user_id, channel_id)
            return

        if not _within_send_rate(user_id):
            logger.warning("WS user %s exceeded the send rate limit", user_id)
            return

        # file_url / file_name / file_size used to be stored exactly as the
        # sender wrote them, with nothing tying them to a real upload. Resolve
        # them against the uploads tree instead; see services/attachments.py.
        try:
            file_url, file_name, file_size = resolve_attachment(db, file_url, file_name)
        except InvalidAttachment as exc:
            logger.warning("WS user %s sent an invalid attachment: %s", user_id, exc)
            return

        content = (content or "")[:MAX_MESSAGE_CHARS]
        if not content and not file_url:
            return

        # Save to database
        msg = Message(
            channel_id=channel_id,
            sender_id=user_id,
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

        # Build broadcast payload while the session is still open
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
        sender_name = user.full_name

    # Session closed — now do the async broadcasts
    for aid in notified_ids:
        await manager.send_personal(aid, {
            "event": "new_notification",
            "data": {
                "title": "New Mention in Chat",
                "body": f"{sender_name} mentioned you in the community chat."
            }
        })

    await manager.broadcast_to_channel(channel_id, broadcast_data)


async def handle_message_reaction(user_id: int, data: dict):
    """Save/delete a reaction and broadcast personalized reaction summaries."""
    message_id = data.get("message_id")
    emoji = data.get("emoji")
    action = data.get("action")

    if not message_id or not emoji or action not in {"add", "remove"}:
        await manager.send_personal(user_id, {
            "event": "reaction_error",
            "data": {"message": "Invalid reaction payload"}
        })
        return

    error_message = None
    channel_id = None
    summaries = {}

    with db_session() as db:
        try:
            message = set_message_reaction(
                db,
                message_id=int(message_id),
                user_id=user_id,
                emoji=emoji,
                action=action,
            )
        except (LookupError, PermissionError, ValueError) as exc:
            error_message = str(exc)
            message = None

        if message is not None:
            channel_id = message.channel_id
            message_id_val = message.id
            subscribers = list(manager.channel_subscriptions.get(channel_id, set()))
            # Compute per-subscriber summaries while the session is open
            summaries = {
                subscriber_id: get_reaction_summary(db, message_id_val, subscriber_id)
                for subscriber_id in subscribers
            }

    if error_message is not None:
        await manager.send_personal(user_id, {
            "event": "reaction_error",
            "data": {"message": error_message}
        })
        return

    for subscriber_id, summary in summaries.items():
        await manager.send_personal(subscriber_id, {
            "event": "reaction_updated",
            "type": "reaction_updated",
            "data": {
                "message_id": int(message_id),
                "reactions_summary": summary,
            }
        })
