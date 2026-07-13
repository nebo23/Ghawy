"""
WebSocket Connection Manager
Handles real-time connections for chat messaging.
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# A stalled client socket (open TCP, not reading — backgrounded phone, dead
# proxy hop) makes a bare `await ws.send_text()` hang FOREVER. Callers like
# POST /chat/messages broadcast while holding a DB session, so one stalled
# socket pins one pooled connection per send until the pool is exhausted and
# the whole site 502s. Every send goes through this bounded wrapper instead.
WS_SEND_TIMEOUT = 5.0


class ConnectionManager:
    """
    Manages active WebSocket connections.
    Maps user_id -> set of WebSocket connections (allows multiple tabs).
    Maps channel_id -> set of user_ids (for broadcasting).
    """

    def __init__(self):
        # user_id -> set of WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # channel_id -> set of user_ids subscribed
        self.channel_subscriptions: Dict[int, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, accept: bool = True):
        """Accept connection and register user. Pass accept=False if already accepted."""
        if accept:
            await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WS connected: user {user_id}  (total users online: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a specific WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # If user has no more active tabs, remove from channels
                for channel_id in list(self.channel_subscriptions.keys()):
                    self.channel_subscriptions[channel_id].discard(user_id)
                    if not self.channel_subscriptions[channel_id]:
                        del self.channel_subscriptions[channel_id]
        logger.info(f"WS disconnected: user {user_id}  (total users online: {len(self.active_connections)})")

    async def disconnect_user(self, user_id: int):
        """Forcefully disconnect all WebSockets for a specific user."""
        if user_id in self.active_connections:
            websockets = list(self.active_connections[user_id])
            for ws in websockets:
                try:
                    await ws.close(code=4003, reason="Account deactivated")
                except Exception:
                    pass
            # The disconnect() method will be called by the finally block in websocket_endpoint
            # But we can also proactively clean up:
            self.active_connections[user_id].clear()
            del self.active_connections[user_id]
            for channel_id in list(self.channel_subscriptions.keys()):
                self.channel_subscriptions[channel_id].discard(user_id)
                if not self.channel_subscriptions[channel_id]:
                    del self.channel_subscriptions[channel_id]
            logger.info(f"WS forcefully disconnected: user {user_id} (total users online: {len(self.active_connections)})")

    def subscribe(self, user_id: int, channel_ids: list):
        """Subscribe a user to a list of channels."""
        for ch_id in channel_ids:
            if ch_id not in self.channel_subscriptions:
                self.channel_subscriptions[ch_id] = set()
            self.channel_subscriptions[ch_id].add(user_id)

    async def _send_bounded(self, ws: WebSocket, user_id: int, message_text: str):
        """Send with a timeout; drop the socket from the manager if it stalls."""
        try:
            await asyncio.wait_for(ws.send_text(message_text), timeout=WS_SEND_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"WS send timed out for user {user_id} — dropping stalled socket")
            self.disconnect(ws, user_id)
        except Exception:
            self.disconnect(ws, user_id)

    async def send_personal(self, user_id: int, data: dict):
        """Send a message to a specific user (all their tabs)."""
        websockets = list(self.active_connections.get(user_id, set()))
        message_text = json.dumps(data, default=str)
        for ws in websockets:
            await self._send_bounded(ws, user_id, message_text)

    async def broadcast_to_channel(self, channel_id: int, data: dict, exclude_user: int = None):
        """Broadcast a message to all users subscribed to a channel."""
        subscribers = self.channel_subscriptions.get(channel_id, set())
        message_text = json.dumps(data, default=str)

        for uid in list(subscribers):
            if uid == exclude_user:
                continue
            websockets = list(self.active_connections.get(uid, set()))
            for ws in websockets:
                await self._send_bounded(ws, uid, message_text)

    async def broadcast_to_all(self, data: dict, exclude_user: int = None):
        """Broadcast a message to every connected user (all their tabs).

        Used for events that are not tied to a real Channel row — e.g. new
        community posts, whose channels are category slugs rather than chat
        Channel records.
        """
        message_text = json.dumps(data, default=str)
        for uid in list(self.active_connections.keys()):
            if uid == exclude_user:
                continue
            for ws in list(self.active_connections.get(uid, set())):
                await self._send_bounded(ws, uid, message_text)

    def get_online_count(self) -> int:
        return len(self.active_connections)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections

# Singleton instance
manager = ConnectionManager()
