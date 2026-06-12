"""
Notification Service — Phase 3
────────────────────────────────
Fire-and-forget Telegram alerts for all trade events.
NEVER blocks strategy execution — all sends are async background tasks.

Message format examples:
  🟢 BUY NIFTY27JUN2423150PE | CE L1 | 1 Lot @ ₹95.50 | NIFTY: 24300 | 10:23 AM
  🎯 TARGET HIT | CE | 3 Lots | +₹4,500 | Exit @ ₹110.50 | 10:47 AM
  🛑 SL HIT | PE L3 | 3 Lots | -₹2,250 | Exit @ ₹75.00 | 11:02 AM
  ⏰ SQUAREOFF | All positions closed | 11:30 AM
  ❌ ERROR | Strategy engine: <message>
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Optional
from loguru import logger
import httpx
import pytz

IST = pytz.timezone("Asia/Kolkata")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class NotificationService:
    def __init__(self):
        self._bot_token: Optional[str] = None
        self._chat_id: Optional[str] = None
        self._enabled: bool = False

        # Per-event toggles (all on by default)
        self._notify_entry: bool = True
        self._notify_target: bool = True
        self._notify_sl: bool = True
        self._notify_squareoff: bool = True
        self._notify_errors: bool = True

    # ── Config ───────────────────────────────────────────────────────────────

    def configure(self, bot_token: str, chat_id: str):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._enabled = bool(bot_token and chat_id)
        logger.info(f"NotificationService configured: enabled={self._enabled}")

    def load_from_db(self):
        """Load Telegram credentials from DB (called on startup and after Settings save)."""
        try:
            from app.db.database import SessionLocal
            from app.models.models import ApiConfig
            from app.services.encryption import decrypt

            with SessionLocal() as db:
                row = db.query(ApiConfig).filter(
                    ApiConfig.provider == "telegram",
                    ApiConfig.is_active == True,
                ).first()
                if row and row.api_key_encrypted:
                    token = decrypt(row.api_key_encrypted)
                    extra = row.extra_config or {}
                    chat_id = extra.get("chat_id", "")
                    if token and chat_id:
                        self.configure(token, chat_id)
                        return
            logger.info("Telegram not configured — notifications disabled")
        except Exception as e:
            logger.warning(f"Telegram config load failed: {e}")

    def is_enabled(self) -> bool:
        return self._enabled

    # ── Event Senders ────────────────────────────────────────────────────────

    def notify_trade_entry(
        self,
        side: str,
        level: str,
        instrument: str,
        lots: int,
        fill_price: Decimal,
        nifty_ltp: Decimal,
    ):
        """Notify: BUY order placed."""
        if not self._enabled or not self._notify_entry:
            return
        emoji = "🟢" if side == "CE" else "🔴"
        msg = (
            f"{emoji} *BUY* `{instrument}`\n"
            f"Side: {side} | Level: {level} | Lots: {lots}\n"
            f"Entry: ₹{fill_price:.2f} | NIFTY: {nifty_ltp:.2f}\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_target_hit(
        self,
        side: str,
        instrument: str,
        lots: int,
        exit_price: Decimal,
        entry_avg: Decimal,
        pnl_rupees: Decimal,
    ):
        """Notify: Target achieved — full position exited."""
        if not self._enabled or not self._notify_target:
            return
        msg = (
            f"🎯 *TARGET HIT* — {side}\n"
            f"Instrument: `{instrument}`\n"
            f"Lots: {lots} | Exit: ₹{exit_price:.2f} | Entry Avg: ₹{entry_avg:.2f}\n"
            f"*P&L: +₹{pnl_rupees:.0f}*\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_sl_hit(
        self,
        side: str,
        instrument: str,
        lots: int,
        exit_price: Decimal,
        entry_avg: Decimal,
        pnl_rupees: Decimal,
    ):
        """Notify: Stop loss triggered at L3."""
        if not self._enabled or not self._notify_sl:
            return
        msg = (
            f"🛑 *SL HIT* — {side} L3\n"
            f"Instrument: `{instrument}`\n"
            f"Lots: {lots} | Exit: ₹{exit_price:.2f} | Entry Avg: ₹{entry_avg:.2f}\n"
            f"*P&L: ₹{pnl_rupees:.0f}*\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_squareoff(self, ce_pnl: Decimal, pe_pnl: Decimal):
        """Notify: 11:30 AM force squareoff."""
        if not self._enabled or not self._notify_squareoff:
            return
        total = ce_pnl + pe_pnl
        sign = "+" if total >= 0 else ""
        msg = (
            f"⏰ *SQUAREOFF — 11:30 AM*\n"
            f"All positions closed.\n"
            f"CE P&L: ₹{ce_pnl:.0f} | PE P&L: ₹{pe_pnl:.0f}\n"
            f"*Total: {sign}₹{total:.0f}*"
        )
        asyncio.create_task(self._send(msg))

    def notify_error(self, context: str, error_msg: str):
        """Notify: Critical error in strategy engine."""
        if not self._enabled or not self._notify_errors:
            return
        msg = (
            f"❌ *ERROR — {context}*\n"
            f"`{error_msg[:200]}`\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_engine_started(self, paper_trade: bool):
        """Notify: Strategy engine started."""
        if not self._enabled:
            return
        mode = "📝 PAPER" if paper_trade else "⚡ LIVE"
        asyncio.create_task(self._send(
            f"▶️ *PyramidStrategy STARTED* — {mode} mode\n"
            f"Time: {self._now_str()}"
        ))

    def notify_engine_stopped(self):
        """Notify: Strategy engine stopped."""
        if not self._enabled:
            return
        asyncio.create_task(self._send(
            f"⏹ *PyramidStrategy STOPPED*\nTime: {self._now_str()}"
        ))

    async def test_connection(self) -> tuple[bool, str]:
        """Send a test message. Returns (success, message)."""
        if not self._enabled:
            return False, "Telegram not configured — set Bot Token and Chat ID in Settings"
        try:
            await self._send("✅ *PyramidStrategy* — Telegram connected successfully!")
            return True, "Test message sent successfully"
        except Exception as e:
            return False, f"Failed: {str(e)}"

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _send(self, text: str):
        """Send a message to Telegram. Fire-and-forget — logs errors but never raises."""
        if not self._bot_token or not self._chat_id:
            return
        try:
            url = TELEGRAM_API.format(token=self._bot_token)
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(url, json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                if resp.status_code != 200:
                    logger.warning(f"Telegram send failed: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"Telegram notification failed (non-critical): {e}")

    def _now_str(self) -> str:
        return datetime.now(IST).strftime("%I:%M %p IST")


# Global singleton
notification_service = NotificationService()