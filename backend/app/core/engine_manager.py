"""
Engine Manager — Multi-User Strategy Engine Registry
Manages active instances of StrategyEngine per user.
Distributes incoming NIFTY spot tick feeds to all active user engines.
"""

import asyncio
from decimal import Decimal
from typing import Optional, Callable, Any
from loguru import logger

from app.core.strategy_engine import StrategyEngine
from app.core.destiny_engine import DestinyStrategyEngine
from app.db.database import SessionLocal
from app.models.models import StrategyConfig


class EngineManager:
    def __init__(self):
        # Maps user_id (int) -> StrategyEngine or DestinyStrategyEngine
        self._engines: dict[int, Any] = {}
        # Global WebSocket broadcast function
        self.broadcast_fn: Optional[Callable] = None

    def get_engine(self, user_id: int) -> Any:
        """Retrieve or instantiate Strategy Engine for a user based on DB strategy_type."""
        if user_id not in self._engines:
            strategy_type = "PYRAMID"
            db = SessionLocal()
            try:
                cfg = db.query(StrategyConfig).filter(
                    StrategyConfig.user_id == user_id,
                    StrategyConfig.is_active == True
                ).order_by(StrategyConfig.id.desc()).first()
                if cfg and getattr(cfg, "strategy_type", None):
                    strategy_type = cfg.strategy_type
            finally:
                db.close()

            logger.info(f"Creating Engine instance ({strategy_type}) for user_id={user_id}")
            if strategy_type == "DESTINY":
                engine = DestinyStrategyEngine(user_id=user_id)
            else:
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
        """Distribute the NIFTY spot tick to all registered engines concurrently."""
        all_engines = []
        tasks = []
        for uid, engine in list(self._engines.items()):
            all_engines.append(engine)
            tasks.append(engine.on_nifty_tick(nifty_ltp))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for engine, res in zip(all_engines, results):
                if isinstance(res, Exception):
                    logger.error(
                        f"User {engine.user_id}: Exception swallowed in on_nifty_tick: {res}",
                        exc_info=res
                    )


# Global singleton manager
engine_manager = EngineManager()
