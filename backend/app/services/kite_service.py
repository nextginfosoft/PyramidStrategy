"""
KiteService — Zerodha Kite Connect Wrapper
Phase 2: Live market data + Paper trade at real prices

Responsibilities:
  - OAuth token management (login URL, request_token exchange)
  - KiteTicker WebSocket: live NIFTY spot + option LTP streaming
  - NFO instrument cache (symbol → token mapping)
  - Option subscription/unsubscription after entry/exit
  - REST LTP fallback when ticker not yet streaming
"""

import asyncio
import threading
from decimal import Decimal
from typing import Optional, Callable
from loguru import logger

from app.config import settings
from app.db.database import get_redis_client
from app.services.encryption import mask_key

# Kite instrument token for NSE:NIFTY 50 spot index
NIFTY_SPOT_TOKEN = 256265


class KiteService:
    """
    Wraps kiteconnect SDK for PyramidStrategy.
    One global instance shared across the app.
    """

    def __init__(self):
        self._kite = None           # KiteConnect REST client
        self._ticker = None         # KiteTicker WebSocket client
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._access_token: Optional[str] = None
        self._is_connected: bool = False
        self._ticker_running: bool = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Async callbacks injected by strategy engine
        self._on_nifty_tick: Optional[Callable] = None   # async (ltp: Decimal)
        self._on_option_tick: Optional[Callable] = None  # async (symbol: str, ltp: Decimal)

        # Instrument cache
        self._token_to_symbol: dict[int, str] = {}
        self._symbol_to_token: dict[str, int] = {}
        self._instruments_loaded: bool = False

        # Option tokens currently subscribed (restored on reconnect)
        self._subscribed_option_tokens: set[int] = set()

        logger.info("KiteService initialized (unauthenticated)")

    # ── Configuration & Auth ─────────────────────────────────────────────────

    def configure(self, api_key: str, api_secret: str):
        """Configure API credentials. Called when user saves Settings."""
        from kiteconnect import KiteConnect
        self._api_key = api_key
        self._api_secret = api_secret
        self._kite = KiteConnect(api_key=api_key)
        logger.info(f"KiteService configured — API key: {mask_key(api_key)}")

    def get_login_url(self) -> str:
        """Return Kite OAuth login URL for the frontend to open."""
        if not self._kite:
            raise RuntimeError("KiteService not configured — save API key/secret in Settings first")
        return self._kite.login_url()

    def exchange_token(self, request_token: str) -> str:
        """Exchange request_token (from OAuth redirect) for access_token."""
        if not self._kite or not self._api_secret:
            raise RuntimeError("KiteService not configured")
        data = self._kite.generate_session(request_token, api_secret=self._api_secret)
        access_token = data["access_token"]
        self._kite.set_access_token(access_token)
        self._access_token = access_token
        logger.info("Kite access_token obtained successfully")
        return access_token

    def set_access_token(self, access_token: str):
        """Restore access_token from DB on app startup."""
        if not self._kite:
            raise RuntimeError("KiteService not configured — call configure() first")
        self._kite.set_access_token(access_token)
        self._access_token = access_token
        logger.info("Kite access_token restored from DB")

    def is_authenticated(self) -> bool:
        return self._kite is not None and self._access_token is not None

    def validate_token(self) -> bool:
        """Validate token with a lightweight Kite API call."""
        try:
            if not self.is_authenticated():
                return False
            self._kite.profile()
            return True
        except Exception as e:
            logger.warning(f"Kite token validation failed: {e}")
            self._access_token = None
            return False

    # ── NFO Instrument Cache ─────────────────────────────────────────────────

    def load_instruments(self):
        """
        Fetch all NFO NIFTY option instruments and cache symbol→token.
        Called at 9:00 AM each morning and on startup if authenticated.
        Downloads ~10k records from Kite (takes a few seconds).
        """
        if not self.is_authenticated():
            logger.warning("Cannot load instruments — Kite not authenticated")
            return

        logger.info("Loading NFO NIFTY instruments from Kite API...")
        try:
            instruments = self._kite.instruments("NFO")
            redis = get_redis_client()
            loaded = 0

            for inst in instruments:
                # Only cache NIFTY options (not futures, not BANKNIFTY)
                if inst.get("name") == "NIFTY" and inst.get("segment") == "NFO-OPT":
                    symbol = inst["tradingsymbol"]
                    token = int(inst["instrument_token"])
                    self._symbol_to_token[symbol] = token
                    self._token_to_symbol[token] = symbol
                    # Redis TTL: 24 hours
                    redis.setex(f"kite:sym:{symbol}", 86400, str(token))
                    redis.setex(f"kite:tok:{token}", 86400, symbol)
                    loaded += 1

            self._instruments_loaded = True
            logger.info(f"Loaded {loaded} NIFTY NFO instruments into cache")

        except Exception as e:
            logger.error(f"Failed to load NFO instruments: {e}")

    def get_instrument_token(self, symbol: str) -> Optional[int]:
        """Resolve option symbol → Kite instrument token (in-memory + Redis fallback)."""
        if symbol in self._symbol_to_token:
            return self._symbol_to_token[symbol]
        # Try Redis cache (survives app restarts)
        try:
            redis = get_redis_client()
            val = redis.get(f"kite:sym:{symbol}")
            if val:
                token = int(val)
                self._symbol_to_token[symbol] = token
                self._token_to_symbol[token] = symbol
                return token
        except Exception:
            pass
        logger.warning(f"Instrument token not found for symbol: {symbol}")
        return None

    # ── KiteTicker WebSocket ─────────────────────────────────────────────────

    def start_ticker(
        self,
        on_nifty_tick: Callable,
        on_option_tick: Callable,
        loop: asyncio.AbstractEventLoop,
    ):
        """
        Start KiteTicker in a background daemon thread.
        kiteconnect SDK is synchronous — we bridge callbacks to asyncio via
        run_coroutine_threadsafe so the strategy engine stays async.
        """
        if not self.is_authenticated():
            raise RuntimeError("Cannot start KiteTicker — Kite not authenticated")
        if self._ticker_running:
            logger.info("KiteTicker already running")
            return

        from kiteconnect import KiteTicker

        self._on_nifty_tick = on_nifty_tick
        self._on_option_tick = on_option_tick
        self._event_loop = loop

        self._ticker = KiteTicker(self._api_key, self._access_token)

        def on_ticks(ws, ticks):
            for tick in ticks:
                token = tick.get("instrument_token")
                ltp = Decimal(str(tick.get("last_price", 0)))
                if ltp == 0:
                    continue

                if token == NIFTY_SPOT_TOKEN:
                    # Dispatch NIFTY tick to strategy engine
                    asyncio.run_coroutine_threadsafe(
                        self._on_nifty_tick(ltp), loop
                    )
                elif token and token in self._token_to_symbol:
                    symbol = self._token_to_symbol[token]
                    # Cache option LTP in Redis (5s TTL for freshness)
                    try:
                        get_redis_client().setex(f"option:ltp:{symbol}", 5, str(ltp))
                    except Exception:
                        pass
                    asyncio.run_coroutine_threadsafe(
                        self._on_option_tick(symbol, ltp), loop
                    )

        def on_connect(ws, response):
            logger.info("✅ KiteTicker connected — subscribing to NIFTY 50 spot")
            self._is_connected = True
            ws.subscribe([NIFTY_SPOT_TOKEN])
            ws.set_mode(ws.MODE_LTP, [NIFTY_SPOT_TOKEN])
            # Re-subscribe to open option positions (e.g. after reconnect)
            if self._subscribed_option_tokens:
                tokens = list(self._subscribed_option_tokens)
                ws.subscribe(tokens)
                ws.set_mode(ws.MODE_LTP, tokens)
                logger.info(f"Re-subscribed {len(tokens)} option tokens on reconnect")

        def on_disconnect(ws, code, reason):
            logger.warning(f"KiteTicker disconnected — code={code} reason={reason}")
            self._is_connected = False

        def on_error(ws, code, reason):
            logger.error(f"KiteTicker error — code={code} reason={reason}")

        def on_reconnect(ws, attempts_count):
            logger.info(f"KiteTicker reconnecting... attempt #{attempts_count}")

        def on_noreconnect(ws):
            logger.error("KiteTicker: max reconnect attempts reached — manual restart needed")
            self._ticker_running = False

        self._ticker.on_ticks = on_ticks
        self._ticker.on_connect = on_connect
        self._ticker.on_disconnect = on_disconnect
        self._ticker.on_error = on_error
        self._ticker.on_reconnect = on_reconnect
        self._ticker.on_noreconnect = on_noreconnect

        thread = threading.Thread(
            target=self._ticker.connect,
            kwargs={"threaded": True},
            daemon=True,
            name="KiteTicker-Thread",
        )
        thread.start()
        self._ticker_running = True
        logger.info("KiteTicker background thread started")

    def subscribe_option(self, symbol: str):
        """
        Subscribe to live tick stream for an option symbol.
        Called immediately after an entry order is placed (Rule: real prices for P&L).
        """
        token = self.get_instrument_token(symbol)
        if token is None:
            logger.warning(f"Cannot subscribe option — token not found: {symbol}")
            return
        self._subscribed_option_tokens.add(token)
        self._token_to_symbol[token] = symbol  # ensure reverse mapping
        if self._ticker and self._is_connected:
            self._ticker.subscribe([token])
            self._ticker.set_mode(self._ticker.MODE_LTP, [token])
            logger.info(f"📊 Subscribed option tick: {symbol} (token={token})")
        else:
            logger.info(f"Queued option subscription (will apply on connect): {symbol}")

    def unsubscribe_option(self, symbol: str):
        """
        Unsubscribe from option tick stream after exit.
        Keeps Redis/memory clean.
        """
        token = self.get_instrument_token(symbol)
        if token and token in self._subscribed_option_tokens:
            self._subscribed_option_tokens.discard(token)
            if self._ticker and self._is_connected:
                self._ticker.unsubscribe([token])
            logger.info(f"Unsubscribed option tick: {symbol}")

    def stop_ticker(self):
        """Stop KiteTicker WebSocket."""
        if self._ticker:
            try:
                self._ticker.stop()
            except Exception as e:
                logger.warning(f"Error stopping KiteTicker: {e}")
        self._ticker_running = False
        self._is_connected = False
        logger.info("KiteTicker stopped")

    # ── REST LTP (fallback) ──────────────────────────────────────────────────

    def get_ltp_rest(self, symbol: str) -> Optional[Decimal]:
        """
        Fetch option LTP via REST API.
        Used as fallback before ticker streams are established.
        Rate-limit: use sparingly (3 req/sec Kite limit).
        """
        if not self.is_authenticated():
            return None
        try:
            resp = self._kite.ltp([f"NFO:{symbol}"])
            ltp = resp.get(f"NFO:{symbol}", {}).get("last_price")
            return Decimal(str(ltp)) if ltp else None
        except Exception as e:
            logger.error(f"REST LTP fetch failed for {symbol}: {e}")
            return None

    def get_option_ltp(self, symbol: str) -> Optional[Decimal]:
        """
        Get option LTP — Redis first (from ticker), REST fallback.
        Returns None if not available.
        """
        try:
            redis = get_redis_client()
            val = redis.get(f"option:ltp:{symbol}")
            if val:
                # Redis returns bytes; decode before converting to Decimal
                val_str = val.decode() if isinstance(val, bytes) else str(val)
                return Decimal(val_str)
        except Exception:
            pass
        # Fallback to REST (slower, limited by rate limit)
        return self.get_ltp_rest(symbol)

    # ── Status ───────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "authenticated": self.is_authenticated(),
            "ticker_connected": self._is_connected,
            "ticker_running": self._ticker_running,
            "instruments_loaded": self._instruments_loaded,
            "subscribed_options": len(self._subscribed_option_tokens),
            "api_key_masked": mask_key(self._api_key) if self._api_key else None,
        }

    def clear_credentials(self):
        """Remove access token (called on logout)."""
        self._access_token = None
        if self._kite:
            try:
                self._kite.set_access_token(None)
            except Exception:
                pass
        self.stop_ticker()


# Global singleton instance
kite_service = KiteService()