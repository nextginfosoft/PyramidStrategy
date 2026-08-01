"""
Gamification Event Listener
────────────────────────────
Passive observer that listens to trade events and dispatches:
1. Motivational quote WebSocket events to the frontend (30-sec popup)
2. Gamified Telegram/WhatsApp messages with quotes

CRITICAL: This module NEVER modifies core strategy logic.
All operations are fire-and-forget with full exception handling.
"""

import asyncio
from typing import Optional, Callable
from loguru import logger

from app.gamification.quotes import (
    get_quote, get_event_type_for_entry, get_event_emoji, get_event_label,
    TARGET_HIT, SL_HIT, SQUAREOFF, ENGINE_START, ENGINE_STOP,
)


class GamificationListener:
    """Passive event listener that dispatches motivational quotes on trade events."""

    def __init__(self):
        self._broadcast_fn: Optional[Callable] = None

    def set_broadcast_fn(self, fn: Callable):
        """Set the WebSocket broadcast function (same as strategy engine uses)."""
        self._broadcast_fn = fn

    async def on_trade_event(
        self,
        user_id: int,
        event_type: str,
        side: str = "",
        level: str = "",
        extra: Optional[dict] = None,
    ):
        """
        Main entry point — called after a trade event occurs.
        Dispatches quote to both WebSocket (frontend popup) and Telegram.
        
        Args:
            user_id: The user ID
            event_type: One of the quote event types (ENTRY_L1, TARGET_HIT, etc.)
            side: CE or PE
            level: The mapped level string (S1/S2/S3/R1/R2/R3)
            extra: Optional dict with additional context (pnl, instrument, etc.)
        """
        try:
            quote_data = get_quote(event_type)
            if not quote_data:
                return

            quote_text, author = quote_data
            emoji = get_event_emoji(event_type)
            label = get_event_label(event_type)

            # 1. Broadcast to frontend via WebSocket
            asyncio.create_task(self._broadcast_to_frontend(
                user_id, event_type, quote_text, author, emoji, label, side, level, extra
            ))

            # 2. Send to Telegram with gamified format
            asyncio.create_task(self._send_telegram_quote(
                user_id, event_type, quote_text, author, emoji, label, side, level, extra
            ))

        except Exception as e:
            logger.warning(f"Gamification event dispatch failed (non-critical): {e}")

    async def _broadcast_to_frontend(
        self, user_id: int, event_type: str,
        quote_text: str, author: str, emoji: str, label: str,
        side: str, level: str, extra: Optional[dict],
    ):
        """Send gamification_event via WebSocket for frontend popup."""
        try:
            if not self._broadcast_fn:
                return

            payload = {
                "type": "gamification_event",
                "user_id": user_id,
                "data": {
                    "event_type": event_type,
                    "quote": quote_text,
                    "author": author,
                    "emoji": emoji,
                    "label": label,
                    "side": side,
                    "level": level,
                    "duration": 30000,  # 30 seconds
                    "extra": extra or {},
                },
            }
            await self._broadcast_fn(user_id, payload)
        except Exception as e:
            logger.warning(f"Gamification WS broadcast failed (non-critical): {e}")

    async def _send_telegram_quote(
        self, user_id: int, event_type: str,
        quote_text: str, author: str, emoji: str, label: str,
        side: str, level: str, extra: Optional[dict],
    ):
        """Send gamified motivational message to Telegram."""
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(user_id)
            if not ns.is_enabled():
                return

            extra = extra or {}

            # Build the gamified Telegram message
            lines = [
                f"🎮 *PYRAMID STRATEGY — MOTIVATION*",
                f"",
                f"{emoji} {label}",
            ]

            if side:
                lines.append(f"Side: {side} | Level: {level}")

            if extra.get("instrument"):
                lines.append(f"Instrument: `{extra['instrument']}`")

            if extra.get("pnl_rupees") is not None:
                pnl = extra["pnl_rupees"]
                sign = "+" if float(str(pnl)) >= 0 else ""
                lines.append(f"P&L: {sign}₹{pnl}")

            lines.extend([
                f"",
                f"💡 _{quote_text}_",
                f"        — *{author}*",
            ])

            # Add special context for certain events
            if event_type == SL_HIT:
                lines.append(f"")
                lines.append(f"⏸ Cool down recommended: 5 minutes")
            elif event_type == "ENTRY_L3" and extra.get("sl_price"):
                lines.append(f"")
                lines.append(f"🛡 SL Active at ₹{extra['sl_price']}")

            msg = "\n".join(lines)
            await ns._send(msg)

        except Exception as e:
            logger.warning(f"Gamification Telegram send failed (non-critical): {e}")

    async def on_entry(self, user_id: int, side: str, level: str, instrument: str = "", fill_price=None, sl_price=None):
        """Convenience method for trade entry events."""
        event_type = get_event_type_for_entry(level)
        extra = {"instrument": instrument}
        if fill_price is not None:
            extra["fill_price"] = str(fill_price)
        if sl_price is not None:
            extra["sl_price"] = str(sl_price)
        await self.on_trade_event(user_id, event_type, side, level, extra)

    async def on_target_hit(self, user_id: int, side: str, instrument: str = "", pnl_rupees=None):
        """Convenience method for target hit events."""
        extra = {"instrument": instrument}
        if pnl_rupees is not None:
            extra["pnl_rupees"] = str(pnl_rupees)
        await self.on_trade_event(user_id, TARGET_HIT, side, extra=extra)

    async def on_sl_hit(self, user_id: int, side: str, instrument: str = "", pnl_rupees=None):
        """Convenience method for SL hit events."""
        extra = {"instrument": instrument}
        if pnl_rupees is not None:
            extra["pnl_rupees"] = str(pnl_rupees)
        await self.on_trade_event(user_id, SL_HIT, side, extra=extra)

    async def on_squareoff(self, user_id: int, total_pnl=None):
        """Convenience method for squareoff events."""
        extra = {}
        if total_pnl is not None:
            extra["pnl_rupees"] = str(total_pnl)
        await self.on_trade_event(user_id, SQUAREOFF, extra=extra)

    async def on_engine_start(self, user_id: int, paper_trade: bool = False):
        """Convenience method for engine start events."""
        extra = {"paper_trade": paper_trade}
        await self.on_trade_event(user_id, ENGINE_START, extra=extra)

    async def on_engine_stop(self, user_id: int):
        """Convenience method for engine stop events."""
        await self.on_trade_event(user_id, ENGINE_STOP)


# Global singleton
gamification_listener = GamificationListener()


def get_gamification_listener() -> GamificationListener:
    """Get the global gamification listener instance."""
    return gamification_listener
