"""
Gamification Hooks
──────────────────
Thin adapter functions that can be called from the strategy engine
to fire gamification events. All calls are fire-and-forget via asyncio.create_task.

Usage in strategy_engine.py (add after existing notification calls):
    from app.gamification.hooks import fire_entry_quote, fire_exit_quote, ...
    asyncio.create_task(fire_entry_quote(user_id, side, level, instrument, fill_price))
"""

import asyncio
from loguru import logger


async def fire_entry_quote(user_id: int, side: str, level: str, instrument: str = "", fill_price=None, sl_price=None):
    """Fire a motivational quote for trade entry. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_entry(user_id, side, level, instrument, fill_price, sl_price)
    except Exception as e:
        logger.warning(f"Gamification entry hook failed (non-critical): {e}")


async def fire_target_quote(user_id: int, side: str, instrument: str = "", pnl_rupees=None):
    """Fire a motivational quote for target hit. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_target_hit(user_id, side, instrument, pnl_rupees)
    except Exception as e:
        logger.warning(f"Gamification target hook failed (non-critical): {e}")


async def fire_sl_quote(user_id: int, side: str, instrument: str = "", pnl_rupees=None):
    """Fire a motivational quote for SL hit. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_sl_hit(user_id, side, instrument, pnl_rupees)
    except Exception as e:
        logger.warning(f"Gamification SL hook failed (non-critical): {e}")


async def fire_squareoff_quote(user_id: int, total_pnl=None):
    """Fire a motivational quote for squareoff. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_squareoff(user_id, total_pnl)
    except Exception as e:
        logger.warning(f"Gamification squareoff hook failed (non-critical): {e}")


async def fire_engine_start_quote(user_id: int, paper_trade: bool = False):
    """Fire a motivational quote for engine start. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_engine_start(user_id, paper_trade)
    except Exception as e:
        logger.warning(f"Gamification engine start hook failed (non-critical): {e}")


async def fire_engine_stop_quote(user_id: int):
    """Fire a motivational quote for engine stop. Non-blocking, fire-and-forget."""
    try:
        from app.gamification.event_listener import get_gamification_listener
        listener = get_gamification_listener()
        await listener.on_engine_stop(user_id)
    except Exception as e:
        logger.warning(f"Gamification engine stop hook failed (non-critical): {e}")
