"""
WebSocket Connection Manager
Handles real-time connections for chat messaging.
"""
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.
    Maps user_id -> WebSocket connection.
    Maps channel_id -> set of user_ids (for broadcasting).
    """

    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # channel_id -> set of user_ids subscribed
        self.channel_subscriptions: Dict[int, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept connection and register user."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WS connected: user {user_id}  (total: {len(self.active_connections)})")

    def disconnect(self, user_id: int):
        """Remove user connection and all channel subscriptions."""
        self.active_connections.pop(user_id, None)
        for channel_id in list(self.channel_subscriptions.keys()):
            self.channel_subscriptions[channel_id].discard(user_id)
            if not self.channel_subscriptions[channel_id]:
                del self.channel_subscriptions[channel_id]
        logger.info(f"WS disconnected: user {user_id}  (total: {len(self.active_connections)})")

    def subscribe(self, user_id: int, channel_ids: list):
        """Subscribe a user to a list of channels."""
        for ch_id in channel_ids:
            if ch_id not in self.channel_subscriptions:
                self.channel_subscriptions[ch_id] = set()
            self.channel_subscriptions[ch_id].add(user_id)

    async def send_personal(self, user_id: int, data: dict):
        """Send a message to a specific user."""
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception:
                self.disconnect(user_id)

    async def broadcast_to_channel(self, channel_id: int, data: dict, exclude_user: int = None):
        """Broadcast a message to all users subscribed to a channel."""
        subscribers = self.channel_subscriptions.get(channel_id, set())
        message_text = json.dumps(data, default=str)

        disconnected = []
        for user_id in subscribers:
            if user_id == exclude_user:
                continue
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    await ws.send_text(message_text)
                except Exception:
                    disconnected.append(user_id)

        # Clean up broken connections
        for uid in disconnected:
            self.disconnect(uid)

    def get_online_count(self) -> int:
        return len(self.active_connections)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections


# Singleton instance
manager = ConnectionManager()
