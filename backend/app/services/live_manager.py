import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class LiveConnectionManager:
    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # session_id -> set of user_ids currently viewing the session
        self.session_viewers: Dict[int, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, accept: bool = True):
        if accept:
            await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)
        # Remove from any sessions they were viewing
        for session_id in list(self.session_viewers.keys()):
            self.session_viewers[session_id].discard(user_id)
            if not self.session_viewers[session_id]:
                del self.session_viewers[session_id]

    def join_session(self, user_id: int, session_id: int):
        if session_id not in self.session_viewers:
            self.session_viewers[session_id] = set()
        self.session_viewers[session_id].add(user_id)

    def leave_session(self, user_id: int, session_id: int):
        if session_id in self.session_viewers:
            self.session_viewers[session_id].discard(user_id)

    def get_viewer_count(self, session_id: int) -> int:
        return len(self.session_viewers.get(session_id, set()))

    async def broadcast_to_session(self, session_id: int, data: dict):
        viewers = self.session_viewers.get(session_id, set())
        message_text = json.dumps(data, default=str)

        disconnected = []
        for user_id in viewers:
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    await ws.send_text(message_text)
                except Exception:
                    disconnected.append(user_id)

        for uid in disconnected:
            self.disconnect(uid)

live_manager = LiveConnectionManager()
