"""
Engine Manager — Multi-User Strategy Engine Registry
Manages active instances of StrategyEngine per (user, underlying).
Distributes incoming NIFTY spot tick feeds to all active NIFTY user engines;
other instruments (BANKNIFTY) get their own engine, wired to the user's Kite
ticker via KiteService.register_instrument_feed.
"""

import asyncio
from decimal import Decimal
from typing import Optional, Callable, Any
from loguru import logger

from app.core.strategy_engine import StrategyEngine
from app.core.destiny_engine import DestinyStrategyEngine
from app.core.instruments import DEFAULT_INSTRUMENT, get_instrument
from app.db.database import SessionLocal
from app.models.models import StrategyConfig


class EngineManager:
    def __init__(self):
        # Maps user_id (int) -> NIFTY StrategyEngine or DestinyStrategyEngine.
        # Kept NIFTY-only and keyed by user_id so existing callers are unchanged.
        self._engines: dict[int, Any] = {}
        # Maps (user_id, underlying) -> engine for every non-NIFTY instrument
        self._instrument_engines: dict[tuple[int, str], Any] = {}
        # Global WebSocket broadcast function
        self.broadcast_fn: Optional[Callable] = None
        # The app's main asyncio event loop, set once at startup (see main.py lifespan).
        # Sync routes and scheduled cron jobs use this to (re)start KiteTicker,
        # which needs a loop reference for thread-safe tick dispatch.
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    def all_engines(self) -> list[Any]:
        """Every engine across all users and instruments."""
        return list(self._engines.values()) + list(self._instrument_engines.values())

    def find_engine(self, user_id: int, underlying: str = DEFAULT_INSTRUMENT) -> Optional[Any]:
        """Existing engine for user + instrument, or None (never creates one)."""
        if underlying == DEFAULT_INSTRUMENT:
            return self._engines.get(user_id)
        return self._instrument_engines.get((user_id, underlying))

    _lookup = find_engine

    def remove_engine(self, user_id: int, underlying: str = DEFAULT_INSTRUMENT) -> Optional[Any]:
        """Drop and return the engine for user + instrument (caller stops it if needed)."""
        if underlying == DEFAULT_INSTRUMENT:
            return self._engines.pop(user_id, None)
        return self._instrument_engines.pop((user_id, underlying), None)

    def engines_for_user(self, user_id: int) -> list[Any]:
        return [e for e in self.all_engines() if e.user_id == user_id]

    def get_engine(self, user_id: int, underlying: str = DEFAULT_INSTRUMENT) -> Any:
        """Retrieve or instantiate the Strategy Engine for a user + instrument based on DB strategy_type."""
        underlying = get_instrument(underlying).name  # validates + normalises
        existing = self._lookup(user_id, underlying)
        if existing is not None:
            return existing

        strategy_type = "PYRAMID"
        db = SessionLocal()
        try:
            cfg = db.query(StrategyConfig).filter(
                StrategyConfig.user_id == user_id,
                StrategyConfig.underlying == underlying,
                StrategyConfig.is_active == True
            ).order_by(StrategyConfig.id.desc()).first()
            if cfg and getattr(cfg, "strategy_type", None):
                strategy_type = cfg.strategy_type
        finally:
            db.close()

        logger.info(f"Creating Engine instance ({strategy_type}/{underlying}) for user_id={user_id}")
        if strategy_type == "DESTINY":
            engine = DestinyStrategyEngine(user_id=user_id, underlying=underlying)
        else:
            engine = StrategyEngine(user_id=user_id, underlying=underlying)

        engine.broadcast_fn = self.broadcast_fn
        if underlying == DEFAULT_INSTRUMENT:
            self._engines[user_id] = engine
        else:
            self._instrument_engines[(user_id, underlying)] = engine
            from app.services.kite_service import get_user_kite_service
            get_user_kite_service(user_id).register_instrument_feed(
                underlying, engine.on_nifty_tick, engine.on_option_tick
            )
        return engine

    def stop_all(self):
        """Stop all running user engines (e.g. on server shutdown)."""
        stopped = 0
        for engine in self.all_engines():
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
            engine for engine in self.all_engines() if engine.is_running
        ]

        if not running_engines:
            logger.warning("emergency_exit_all called but no engines are running.")
            return []

        async def _exit_one(engine: StrategyEngine) -> dict:
            try:
                result = await engine.emergency_exit()
                return {"user_id": engine.user_id, "underlying": engine.underlying, **result}
            except Exception as exc:
                logger.error(
                    f"emergency_exit_all: error for user {engine.user_id}: {exc}",
                    exc_info=exc,
                )
                return {
                    "user_id": engine.user_id,
                    "underlying": engine.underlying,
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
