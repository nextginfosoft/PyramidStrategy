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


def escape_markdown(text: str) -> str:
    """Escape special markdown v1 characters for Telegram."""
    if not text:
        return ""
    # For Telegram Markdown v1, the characters to escape are: \, _, *, [, `
    for char in ('\\', '_', '*', '[', '`'):
        text = text.replace(char, f"\\{char}")
    return text


class NotificationService:
    def __init__(self, user_id: int = 1):
        self.user_id = user_id
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
        logger.info(f"NotificationService configured for User {self.user_id}: enabled={self._enabled}")

    def load_from_db(self):
        """Load Telegram and WhatsApp credentials from DB (called on startup and after Settings save)."""
        try:
            from app.db.database import SessionLocal
            from app.models.models import ApiConfig
            from app.services.encryption import decrypt
            from app.services.whatsapp import get_user_whatsapp_service

            # Load WhatsApp config
            self._ws = get_user_whatsapp_service(self.user_id)
            self._ws.load_from_db()

            with SessionLocal() as db:
                row = db.query(ApiConfig).filter(
                    ApiConfig.user_id == self.user_id,
                    ApiConfig.provider == "telegram",
                    ApiConfig.is_active == True,
                ).first()
                if row and row.api_key_encrypted:
                    token = decrypt(row.api_key_encrypted)
                    extra = row.extra_config or {}
                    chat_id = extra.get("chat_id", "")
                    if token and chat_id:
                        self.configure(token, chat_id)
                        self._enabled = True
                        return

            self._bot_token = None
            self._chat_id = None
            self._enabled = self._ws.is_enabled()
            if not self._enabled:
                logger.info(f"User {self.user_id}: Neither Telegram nor WhatsApp configured — notifications disabled")
        except Exception as e:
            logger.warning(f"User {self.user_id}: Config load failed: {e}")
            self._enabled = False

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
        strategy_type: str = "PYRAMID",
    ):
        """Notify: BUY order placed."""
        if not self._enabled or not self._notify_entry:
            return
        emoji = "🟢" if side == "CE" else "🔴"
        strat_badge = "🌌 *[DESTINY]*" if strategy_type == "DESTINY" else "🔺 *[PYRAMID]*"
        
        # Convert L1/L2/L3 to S1/S2/S3 for CE, or R1/R2/R3 for PE
        mapped_lvl = level
        if level in ("L1", "L2", "L3"):
            prefix = "S" if side == "CE" else "R"
            mapped_lvl = level.replace("L", prefix)

        msg = (
            f"{emoji} {strat_badge} *BUY* `{instrument}`\n"
            f"Side: {side} | Level: {mapped_lvl} | Lots: {lots}\n"
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
        strategy_type: str = "PYRAMID",
    ):
        """Notify: Target achieved — full position exited."""
        if not self._enabled or not self._notify_target:
            return
        strat_badge = "🌌 *[DESTINY]*" if strategy_type == "DESTINY" else "🔺 *[PYRAMID]*"
        msg = (
            f"🎯 {strat_badge} *TARGET HIT* — {side}\n"
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
        strategy_type: str = "PYRAMID",
    ):
        """Notify: Stop loss triggered."""
        if not self._enabled or not self._notify_sl:
            return
        strat_badge = "🌌 *[DESTINY]*" if strategy_type == "DESTINY" else "🔺 *[PYRAMID]*"
        prefix = "S" if side == "CE" else "R"
        mapped_lvl = f"{prefix}3"
        msg = (
            f"🛑 {strat_badge} *SL HIT* — {side} {mapped_lvl}\n"
            f"Instrument: `{instrument}`\n"
            f"Lots: {lots} | Exit: ₹{exit_price:.2f} | Entry Avg: ₹{entry_avg:.2f}\n"
            f"*P&L: ₹{pnl_rupees:.0f}*\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_squareoff(self, ce_pnl: Decimal, pe_pnl: Decimal, squareoff_time_str: str = "11:30", strategy_type: str = "PYRAMID"):
        """Notify: force squareoff at configured time."""
        if not self._enabled or not self._notify_squareoff:
            return
        strat_badge = "🌌 *[DESTINY]*" if strategy_type == "DESTINY" else "🔺 *[PYRAMID]*"
        total = ce_pnl + pe_pnl
        sign = "+" if total >= 0 else ""
        msg = (
            f"⏰ {strat_badge} *SQUAREOFF — {squareoff_time_str}*\n"
            f"All positions closed.\n"
            f"CE P&L: ₹{ce_pnl:.0f} | PE P&L: ₹{pe_pnl:.0f}\n"
            f"*Total: {sign}₹{total:.0f}*"
        )
        asyncio.create_task(self._send(msg))

    def notify_error(self, context: str, error_msg: str, strategy_type: str = "PYRAMID"):
        """Notify: Critical error in strategy engine."""
        if not self._enabled or not self._notify_errors:
            return
        strat_badge = "🌌 *[DESTINY]*" if strategy_type == "DESTINY" else "🔺 *[PYRAMID]*"
        msg = (
            f"❌ {strat_badge} *ERROR — {context}*\n"
            f"`{error_msg[:200]}`\n"
            f"Time: {self._now_str()}"
        )
        asyncio.create_task(self._send(msg))

    def notify_engine_started(self, paper_trade: bool, strategy_type: str = "PYRAMID"):
        """Notify: Strategy engine started."""
        if not self._enabled:
            return
        mode = "📝 PAPER" if paper_trade else "⚡ LIVE"
        strat_name = "DestinyStrategy" if strategy_type == "DESTINY" else "PyramidStrategy"
        strat_badge = "🌌" if strategy_type == "DESTINY" else "🔺"
        asyncio.create_task(self._send(
            f"▶️ {strat_badge} *{strat_name} STARTED* — {mode} mode\n"
            f"Time: {self._now_str()}"
        ))

    def notify_engine_stopped(self, strategy_type: str = "PYRAMID"):
        """Notify: Strategy engine stopped."""
        if not self._enabled:
            return
        strat_name = "DestinyStrategy" if strategy_type == "DESTINY" else "PyramidStrategy"
        strat_badge = "🌌" if strategy_type == "DESTINY" else "🔺"
        asyncio.create_task(self._send(
            f"⏹ {strat_badge} *{strat_name} STOPPED*\nTime: {self._now_str()}"
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
        """Send message to Telegram and/or WhatsApp. Fire-and-forget — logs errors but never raises."""
        # 1. Telegram
        if self._bot_token and self._chat_id:
            try:
                url = TELEGRAM_API.format(token=self._bot_token)
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.post(url, json={
                        "chat_id": self._chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    })
                    if resp.status_code != 200:
                        logger.warning(f"User {self.user_id}: Telegram send failed: {resp.status_code} {resp.text[:100]}")
                        if resp.status_code == 400:
                            try:
                                resp_data = resp.json()
                                new_chat_id = resp_data.get("parameters", {}).get("migrate_to_chat_id")
                                if new_chat_id:
                                    logger.info(f"User {self.user_id}: Migrating Telegram Chat ID from {self._chat_id} to supergroup ID {new_chat_id}...")
                                    self._chat_id = str(new_chat_id)
                                    
                                    # Update in database
                                    from app.db.database import SessionLocal
                                    from app.models.models import ApiConfig
                                    with SessionLocal() as db:
                                        row = db.query(ApiConfig).filter(
                                            ApiConfig.user_id == self.user_id,
                                            ApiConfig.provider == "telegram",
                                            ApiConfig.is_active == True,
                                        ).first()
                                        if row:
                                            # We query directly to avoid state desync
                                            db.refresh(row)
                                            # Update extra config
                                            from sqlalchemy.orm.attributes import flag_modified
                                            extra = row.extra_config or {}
                                            extra["chat_id"] = str(new_chat_id)
                                            row.extra_config = extra
                                            flag_modified(row, "extra_config")
                                            db.commit()
                                            logger.info(f"User {self.user_id}: Updated ApiConfig in DB with migrated Chat ID")
                                            
                                    # Re-send message to new chat_id
                                    resp = await client.post(url, json={
                                        "chat_id": self._chat_id,
                                        "text": text,
                                        "parse_mode": "Markdown",
                                    })
                                    if resp.status_code == 200:
                                        logger.info(f"User {self.user_id}: Resent Telegram message to migrated supergroup successfully")
                            except Exception as migrate_ex:
                                logger.error(f"Error handling group chat migration: {migrate_ex}")
            except Exception as e:
                logger.warning(f"User {self.user_id}: Telegram notification failed (non-critical): {e}")

        # 2. WhatsApp
        if hasattr(self, "_ws") and self._ws.is_enabled():
            try:
                await self._ws.send_message(text)
            except Exception as e:
                logger.warning(f"User {self.user_id}: WhatsApp notification failed (non-critical): {e}")

    def _now_str(self) -> str:
        return datetime.now(IST).strftime("%I:%M %p IST")


# Global user instance cache
_user_instances: dict[int, NotificationService] = {}


def get_user_notification_service(user_id: int) -> NotificationService:
    """Get or create NotificationService instance for a specific user."""
    if user_id not in _user_instances:
        _user_instances[user_id] = NotificationService(user_id)
    return _user_instances[user_id]


# Global singleton (defaults to user_id=1 for backward compatibility/tests)
notification_service = NotificationService(1)