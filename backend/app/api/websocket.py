"""
WebSocket endpoint — pushes real-time updates to all connected frontend clients.
Events: nifty_tick, trade_event, strategy_status, ai_suggestion, error
"""

import asyncio
import json
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from jose import jwt, JWTError

from app.config import settings
from app.api.routes.session import JWT_ALGORITHM


def get_user_id_from_token(token: str) -> Optional[int]:
    """Helper to verify JWT token and retrieve user_id."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        return int(user_id_str) if user_id_str else None
    except (JWTError, ValueError):
        return None


class ConnectionManager:
    def __init__(self):
        # Maps user_id (int) -> list of active WebSockets
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: int):
        await ws.accept()
        if user_id not in self.active:
            self.active[user_id] = []
        self.active[user_id].append(ws)
        logger.info(f"WS client connected for User {user_id}. Active connections for user: {len(self.active[user_id])}")

    def disconnect(self, ws: WebSocket, user_id: int):
        if user_id in self.active and ws in self.active[user_id]:
            self.active[user_id].remove(ws)
            if not self.active[user_id]:
                del self.active[user_id]
        logger.info(f"WS client disconnected for User {user_id}.")

    async def broadcast(self, user_id: int, message: dict):
        """Send message only to active WebSockets of the matching user_id."""
        if user_id not in self.active:
            return
        text = json.dumps(message, default=str)
        dead = []
        for ws in list(self.active[user_id]):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("WS connection rejected: No token provided in query parameters")
        await websocket.close(code=4001)
        return

    user_id = get_user_id_from_token(token)
    if not user_id:
        logger.warning("WS connection rejected: Invalid/expired token")
        await websocket.close(code=4002)
        return

    await manager.connect(websocket, user_id)

    # Ensure engine manager and user engine are configured to use this broadcast method
    from app.core.engine_manager import engine_manager
    engine_manager.broadcast_fn = manager.broadcast

    user_engine = engine_manager.get_engine(user_id)
    user_engine.broadcast_fn = manager.broadcast

    # Wire gamification listener to use the same broadcast function
    try:
        from app.gamification.event_listener import get_gamification_listener
        get_gamification_listener().set_broadcast_fn(manager.broadcast)
    except Exception:
        pass  # Gamification is non-critical

    # Send current status immediately on connect
    try:
        status = user_engine.get_full_status()
        await websocket.send_text(json.dumps({
            "type": "strategy_status",
            "data": status,
        }, default=str))
    except Exception as e:
        logger.warning(f"Failed to send initial status to User {user_id} WS: {e}")

    try:
        while True:
            # Keep connection alive; client can send commands
            data = await websocket.receive_text()
            await _handle_client_message(websocket, user_id, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


async def _handle_client_message(ws: WebSocket, user_id: int, raw: str):
    """Handle messages sent FROM frontend to backend via WS."""
    try:
        msg = json.loads(raw)
        cmd = msg.get("command")

        if cmd == "ping":
            await ws.send_text(json.dumps({"type": "pong"}))
        elif cmd == "get_status":
            from app.core.engine_manager import engine_manager
            user_engine = engine_manager.get_engine(user_id)
            status = user_engine.get_full_status()
            await ws.send_text(json.dumps({"type": "strategy_status", "data": status}, default=str))

    except Exception as e:
        logger.error(f"WS message handling error for User {user_id}: {e}")
