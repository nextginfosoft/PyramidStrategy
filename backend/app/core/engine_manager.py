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

    async def emergency_exit_all(self) -> list[dict]:
        """Force-close all open positions across every active user engine concurrently.

        Returns a list of per-user result dicts, each containing:
            user_id, status, exited_count, pnl_rupees  (or an error key on failure).
        """
        running_engines = [
            engine for engine in self._engines.values() if engine.is_running
        ]

        if not running_engines:
            logger.warning("emergency_exit_all called but no engines are running.")
            return []

        async def _exit_one(engine: StrategyEngine) -> dict:
            try:
                result = await engine.emergency_exit()
                return {"user_id": engine.user_id, **result}
            except Exception as exc:
                logger.error(
                    f"emergency_exit_all: error for user {engine.user_id}: {exc}",
                    exc_info=exc,
                )
                return {
                    "user_id": engine.user_id,
                    "status": "error",
                    "error": str(exc),
                }

        results = await asyncio.gather(*[_exit_one(e) for e in running_engines])
        logger.warning(
            f"emergency_exit_all: processed {len(running_engines)} engine(s). "
            f"Results: {results}"
        )
        return list(results)

    async def broadcast_nifty_tick(self, nifty_ltp: Decimal):
        """Distribute the NIFTY spot tick to all running engines concurrently."""
        running_engines = []
        tasks = []
        for uid, engine in list(self._engines.items()):
            if engine.is_running:
                running_engines.append(engine)
                tasks.append(engine.on_nifty_tick(nifty_ltp))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for engine, res in zip(running_engines, results):
                if isinstance(res, Exception):
                    logger.error(
                        f"User {engine.user_id}: Exception swallowed in on_nifty_tick: {res}",
                        exc_info=res
                    )


# Global singleton manager
engine_manager = EngineManager()
