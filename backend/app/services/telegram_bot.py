import asyncio
import time
import httpx
from decimal import Decimal
from typing import Optional
from loguru import logger

from app.db.database import SessionLocal
from app.models.models import ApiConfig
from app.services.encryption import decrypt
from app.core.engine_manager import engine_manager

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"

# Security Guard: Only allow commands from your specific Telegram User ID
AUTHORIZED_USER_IDS = {472529253}


class TelegramBotService:
    def __init__(self):
        self._bot_token: Optional[str] = None
        self._chat_id: Optional[str] = None
        self._enabled: bool = False
        self._last_update_id: int = 0
        self._polling_task: Optional[asyncio.Task] = None

    def load_config(self):
        """Load Telegram configuration credentials from DB."""
        try:
            with SessionLocal() as db:
                row = db.query(ApiConfig).filter(
                    ApiConfig.user_id == 1,
                    ApiConfig.provider == "telegram",
                    ApiConfig.is_active == True,
                ).first()
                if row and row.api_key_encrypted:
                    self._bot_token = decrypt(row.api_key_encrypted)
                    extra = row.extra_config or {}
                    self._chat_id = str(extra.get("chat_id", ""))
                    self._enabled = bool(self._bot_token and self._chat_id)
        except Exception as e:
            logger.warning(f"TelegramBotService config load failed: {e}")
            self._enabled = False

    async def start(self):
        """Start the background long polling listener task."""
        self.load_config()
        if not self._enabled:
            logger.info("TelegramBotService: Bot not configured or disabled. Polling disabled.")
            return

        logger.info("TelegramBotService: Starting background polling task...")
        self._polling_task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Stop the background polling task."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            logger.info("TelegramBotService: Background polling stopped.")

    async def _send_message(self, chat_id: str, text: str, reply_markup: Optional[dict] = None):
        """Send a formatted message to Telegram with optional inline buttons."""
        try:
            url = TELEGRAM_API_URL.format(token=self._bot_token, method="sendMessage")
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"TelegramBotService send message failed: {e}")

    async def _poll_loop(self):
        """Main update polling loop."""
        url = TELEGRAM_API_URL.format(token=self._bot_token, method="getUpdates")
        client = httpx.AsyncClient(timeout=15)

        # Get initial offset
        try:
            resp = await client.get(url, params={"limit": 1, "timeout": 0})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    self._last_update_id = data["result"][-1]["update_id"]
        except Exception as e:
            logger.warning(f"TelegramBotService initial update check failed: {e}")

        logger.info(f"TelegramBotService: Polling initialized (offset={self._last_update_id})")

        while True:
            try:
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": 10,
                }
                resp = await client.get(url, params=params, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok") and data.get("result"):
                        for update in data["result"]:
                            self._last_update_id = update["update_id"]
                            await self._handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"TelegramBotService polling error: {e}")
                await asyncio.sleep(5)  # Error cooldown

        await client.aclose()

    async def _handle_update(self, update: dict):
        """Verify, sanitize, and route updates."""
        message = update.get("message")
        callback_query = update.get("callback_query")

        chat_id = None
        user_id = None
        text = None
        callback_data = None

        if message:
            chat_id = str(message["chat"]["id"])
            user_id = message["from"]["id"]
            text = message.get("text", "").strip()
        elif callback_query:
            chat_id = str(callback_query["message"]["chat"]["id"])
            user_id = callback_query["from"]["id"]
            callback_data = callback_query.get("data", "")

        if not chat_id or not user_id:
            return

        # Security Gating 1: Verify message comes from authorized chat ID (group/channel or direct DM)
        if chat_id != self._chat_id:
            logger.warning(f"TelegramBotService: Blocked command from unauthorized chat_id={chat_id}")
            return

        # Determine if action is state-modifying (start/stop) or query-only (status/pnl)
        is_write_action = False
        if text:
            is_write_action = text.startswith("/start") or text.startswith("/stop")
        elif callback_data:
            is_write_action = callback_data in ("btn_start", "btn_stop")

        # Security Gating 2: Restrict write actions to authorized administrators (you, Santosh)
        if is_write_action and user_id not in AUTHORIZED_USER_IDS:
            logger.warning(f"TelegramBotService: Blocked state-modifying command from unauthorized user_id={user_id}")
            await self._send_message(chat_id, "⚠️ Only authorized administrators are permitted to start/stop the trading engine.")
            return

        if text:
            await self._process_command(chat_id, text)
        elif callback_data:
            await self._process_callback(chat_id, callback_query["id"], callback_data, user_id)

    async def _process_command(self, chat_id: str, text: str):
        """Interpret text commands."""
        engine = engine_manager.get_engine(1)  # User 1

        if text.startswith("/start"):
            if engine.is_running:
                await self._send_message(chat_id, "⚠️ *PyramidStrategy* is already running.")
            else:
                engine.start()
                await self._send_message(chat_id, "▶️ *PyramidStrategy STARTED* successfully.")

        elif text.startswith("/stop"):
            if not engine.is_running:
                await self._send_message(chat_id, "⚠️ *PyramidStrategy* is already stopped.")
            else:
                engine.stop()
                await self._send_message(chat_id, "⏹ *PyramidStrategy STOPPED* successfully.")

        elif text.startswith("/status") or text.startswith("/pnl"):
            status = engine.get_full_status()
            is_running = "🟢 RUNNING" if status.get("is_running") else "🔴 STOPPED"
            mode = "📝 PAPER" if status.get("paper_trade") else "⚡ LIVE"
            ltp = status.get("nifty_ltp")
            ltp_str = f"₹{ltp:.2f}" if ltp else "N/A"

            ce = status.get("ce") or {}
            ce_lots = ce.get("lots", 0)
            ce_avg = ce.get("entry_avg_price") or 0.0
            ce_pnl = Decimal(str(ce.get("unrealized_pnl") or 0.0)) + Decimal(str(ce.get("realized_pnl") or 0.0))

            pe = status.get("pe") or {}
            pe_lots = pe.get("lots", 0)
            pe_avg = pe.get("entry_avg_price") or 0.0
            pe_pnl = Decimal(str(pe.get("unrealized_pnl") or 0.0)) + Decimal(str(pe.get("realized_pnl") or 0.0))

            total_pnl = ce_pnl + pe_pnl
            pnl_sign = "+" if total_pnl >= 0 else ""

            msg = (
                f"📊 *PyramidStrategy Status*\n"
                f"───────────────────\n"
                f"Engine: {is_running} | {mode}\n"
                f"NIFTY Spot: *{ltp_str}*\n\n"
                f"🟢 *CE Leg*:\n"
                f"  Lots: {ce_lots} | Avg: ₹{ce_avg:.2f}\n"
                f"  P&L: ₹{ce_pnl:+.2f}\n\n"
                f"🔴 *PE Leg*:\n"
                f"  Lots: {pe_lots} | Avg: ₹{pe_avg:.2f}\n"
                f"  P&L: ₹{pe_pnl:+.2f}\n"
                f"───────────────────\n"
                f"💰 *Total P&L: {pnl_sign}₹{total_pnl:.2f}*"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "▶️ Start Engine", "callback_data": "btn_start"},
                        {"text": "⏹ Stop Engine", "callback_data": "btn_stop"},
                    ],
                    [
                        {"text": "🔄 Refresh Status", "callback_data": "btn_refresh"},
                    ]
                ]
            }
            await self._send_message(chat_id, msg, reply_markup=keyboard)

        else:
            help_msg = (
                f"🤖 *PyramidStrategy Bot Controls*:\n"
                f"You can use these commands:\n"
                f"• `/status` - Check status, positions & live P&L\n"
                f"• `/start` - Start the trading engine\n"
                f"• `/stop` - Stop the trading engine"
            )
            await self._send_message(chat_id, help_msg)

    async def _process_callback(self, chat_id: str, query_id: str, callback_data: str, user_id: int):
        """Interpret button clicks (Callback Queries)."""
        try:
            url = TELEGRAM_API_URL.format(token=self._bot_token, method="answerCallbackQuery")
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json={"callback_query_id": query_id})
        except Exception:
            pass

        # Verify buttons write actions inside callback
        if callback_data in ("btn_start", "btn_stop") and user_id not in AUTHORIZED_USER_IDS:
            await self._send_message(chat_id, "⚠️ Only authorized administrators are permitted to start/stop the trading engine.")
            return

        engine = engine_manager.get_engine(1)

        if callback_data == "btn_start":
            if engine.is_running:
                await self._send_message(chat_id, "⚠️ *PyramidStrategy* is already running.")
            else:
                engine.start()
                await self._send_message(chat_id, "▶️ *PyramidStrategy STARTED* successfully.")

        elif callback_data == "btn_stop":
            if not engine.is_running:
                await self._send_message(chat_id, "⚠️ *PyramidStrategy* is already stopped.")
            else:
                engine.stop()
                await self._send_message(chat_id, "⏹ *PyramidStrategy STOPPED* successfully.")

        elif callback_data == "btn_refresh":
            await self._process_command(chat_id, "/status")


telegram_bot_service = TelegramBotService()
