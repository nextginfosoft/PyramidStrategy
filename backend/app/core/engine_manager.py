"""
Engine Manager — Multi-User Strategy Engine Registry
Manages active instances of StrategyEngine per user.
Distributes incoming NIFTY spot tick feeds to all active user engines.
"""

import asyncio
from decimal import Decimal
from typing import Optional, Callable
from loguru import logger

from app.core.strategy_engine import StrategyEngine


class EngineManager:
    def __init__(self):
        # Maps user_id (int) -> StrategyEngine
        self._engines: dict[int, StrategyEngine] = {}
        # Global WebSocket broadcast function
        self.broadcast_fn: Optional[Callable] = None

    def get_engine(self, user_id: int) -> StrategyEngine:
        """Retrieve or instantiate StrategyEngine for a user."""
        if user_id not in self._engines:
            logger.info(f"Creating StrategyEngine instance for user_id={user_id}")
            engine = StrategyEngine(user_id=user_id)
            engine.broadcast_fn = self.broadcast_fn
            self._engines[user_id] = engine
        return self._engines[user_id]

    def stop_all(self):
        """Stop all running user engines (e.g. on server shutdown)."""
        stopped = 0
        for uid, engine in list(self._engines.items()):
            if engine.is_running:
                engine.stop()
                stopped += 1
        logger.info(f"Stopped {stopped} user engines.")

    async def broadcast_nifty_tick(self, nifty_ltp: Decimal):
        """Distribute the NIFTY spot tick to all running engines concurrently."""
        tasks = []
        for uid, engine in list(self._engines.items()):
            if engine.is_running:
                tasks.append(engine.on_nifty_tick(nifty_ltp))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global singleton manager
engine_manager = EngineManager()
