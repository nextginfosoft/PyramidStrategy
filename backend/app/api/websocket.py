"""
WebSocket endpoint — pushes real-time updates to all connected frontend clients.
Events: nifty_tick, trade_event, strategy_status, ai_suggestion, error
"""

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from app.core.strategy_engine import engine


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WS client disconnected. Remaining: {len(self.active)}")

    async def broadcast(self, message: dict):
        if not self.active:
            return
        text = json.dumps(message, default=str)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Inject broadcaster into strategy engine
    engine.broadcast_fn = manager.broadcast

    # Send current status immediately on connect
    try:
        status = engine.get_full_status()
        await websocket.send_text(json.dumps({
            "type": "strategy_status",
            "data": status,
        }, default=str))
    except Exception:
        pass

    try:
        while True:
            # Keep connection alive; client can send commands
            data = await websocket.receive_text()
            await _handle_client_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def _handle_client_message(ws: WebSocket, raw: str):
    """Handle messages sent FROM frontend to backend via WS."""
    try:
        msg = json.loads(raw)
        cmd = msg.get("command")

        if cmd == "ping":
            await ws.send_text(json.dumps({"type": "pong"}))
        elif cmd == "get_status":
            status = engine.get_full_status()
            await ws.send_text(json.dumps({"type": "strategy_status", "data": status}, default=str))

    except Exception as e:
        logger.error(f"WS message handling error: {e}")
