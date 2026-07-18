"""
KiteService — Zerodha Kite Connect Wrapper
Phase 2: Live market data + Paper trade at real prices

Multi-User version: cached per user_id.
"""

import asyncio
import time
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
    Instantiated per user.
    """

    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self._kite = None           # KiteConnect REST client
        self._ticker = None         # KiteTicker WebSocket client
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._access_token: Optional[str] = None
        self._is_connected: bool = False
        self._ticker_running: bool = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        self._last_api_error: Optional[str] = None
        self._last_ticker_error: Optional[str] = None
        self._last_nifty_tick_time: Optional[float] = None

        # Async callbacks injected by strategy engine
        self._on_nifty_tick: Optional[Callable] = None   # async (ltp: Decimal)
        self._on_option_tick: Optional[Callable] = None  # async (symbol: str, ltp: Decimal)

        # Instrument cache (symbol ↔ token)
        self._token_to_symbol: dict[int, str] = {}
        self._symbol_to_token: dict[str, int] = {}
        self._instruments_loaded: bool = False

        # Option tokens currently subscribed (restored on reconnect)
        self._subscribed_option_tokens: set[int] = set()

        # REST LTP cache to prevent rate limiting (symbol -> (timestamp, value))
        self._rest_ltp_cache: dict[str, tuple[float, Optional[Decimal]]] = {}

        # Available margin cache (to prevent rate limits)
        self._available_margin: Optional[float] = None
        self._last_margin_fetch_time: float = 0.0

        logger.info(f"KiteService initialized for User {user_id} (unauthenticated)")

    @property
    def kite(self):
        """Expose the underlying KiteConnect REST client."""
        return self._kite

    @kite.setter
    def kite(self, value):
        self._kite = value

    # ── Configuration & Auth ─────────────────────────────────────────────────

    def configure(self, api_key: str, api_secret: str):
        """Configure API credentials. Called when user saves Settings."""
        from kiteconnect import KiteConnect
        self._api_key = api_key
        self._api_secret = api_secret
        self._kite = KiteConnect(api_key=api_key)
        logger.info(f"KiteService configured for User {self.user_id} — API key: {mask_key(api_key)}")

    def get_login_url(self) -> str:
        """Return Kite OAuth login URL for the frontend to open."""
        if not self._kite:
            raise RuntimeError(f"KiteService not configured for User {self.user_id} — save API credentials first")
        base_url = self._kite.login_url()
        return f"{base_url}&redirect_params=user_id%3D{self.user_id}"

    def exchange_token(self, request_token: str) -> str:
        """Exchange request_token (from OAuth redirect) for access_token."""
        if not self._kite or not self._api_secret:
            raise RuntimeError("KiteService not configured")
        data = self._kite.generate_session(request_token, api_secret=self._api_secret)
        access_token = data["access_token"]
        self._kite.set_access_token(access_token)
        self._access_token = access_token
        logger.info(f"User {self.user_id}: Kite access_token obtained successfully")
        return access_token

    def auto_login(self, username: str, password: str, totp_secret: str) -> str:
        """
        Perform automated Zerodha login using password and TOTP,
        generating request_token, exchanging it, and returning the access_token.
        """
        import requests
        import pyotp
        import urllib.parse

        if not self._api_key or not self._api_secret:
            raise RuntimeError("KiteService is not configured (missing API Key/Secret)")

        logger.info(f"User {self.user_id}: Starting automated TOTP login for {username}...")

        session = requests.Session()
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/x-www-form-urlencoded"
        }
        session.headers.update(headers)

        # 1. Access login page to fetch initial cookies
        try:
            session.get("https://kite.zerodha.com")
        except Exception as e:
            raise RuntimeError(f"Failed to access Zerodha login page: {e}")

        # 2. POST to api/login
        try:
            login_res = session.post(
                "https://kite.zerodha.com/api/login",
                data={"user_id": username, "password": password}
            )
            login_data = login_res.json()
        except Exception as e:
            raise RuntimeError(f"Failed to submit login credentials: {e}")

        if login_data.get("status") != "success":
            raise RuntimeError(f"Login API error: {login_data.get('message', 'Unknown error')}")

        request_id = login_data["data"]["request_id"]
        logger.info(f"User {self.user_id}: Got login request_id: {request_id}")

        # 3. Generate TOTP code
        try:
            secret_clean = totp_secret.strip()
            # If the user pasted an otpauth URI, parse the secret param
            if secret_clean.lower().startswith("otpauth://"):
                parsed_otp = urllib.parse.urlparse(totp_secret)
                otp_params = urllib.parse.parse_qs(parsed_otp.query)
                secret_param = otp_params.get("secret")
                if secret_param:
                    secret_clean = secret_param[0]
            
            secret_clean = secret_clean.replace(" ", "").upper()
            # Ensure base32 padding is correct (multiple of 8)
            missing_padding = len(secret_clean) % 8
            if missing_padding:
                secret_clean += "=" * (8 - missing_padding)
                
            totp = pyotp.TOTP(secret_clean)
            otp_val = totp.now()
        except Exception as e:
            raise RuntimeError(f"Failed to generate TOTP code (check secret key): {e}")

        # 4. POST to api/twofa
        try:
            twofa_res = session.post(
                "https://kite.zerodha.com/api/twofa",
                data={
                    "user_id": username,
                    "request_id": request_id,
                    "twofa_value": otp_val,
                    "twofa_type": "totp"
                }
            )
            twofa_data = twofa_res.json()
        except Exception as e:
            raise RuntimeError(f"Failed to submit 2FA details: {e}")

        if twofa_data.get("status") != "success":
            raise RuntimeError(f"2FA API error: {twofa_data.get('message', 'Unknown error')}")

        logger.info(f"User {self.user_id}: 2FA validation successful")

        # 5. Connect to Kite Connect authorization URL and follow redirects step-by-step
        auth_url = f"https://kite.zerodha.com/connect/login?api_key={self._api_key}&v=3"
        current_url = auth_url
        request_token = None
        max_redirects = 5

        for redirect_count in range(max_redirects):
            try:
                auth_res = session.get(current_url, allow_redirects=False)
            except Exception as e:
                raise RuntimeError(f"Failed to load Kite auth URL {current_url}: {e}")

            if auth_res.status_code in (301, 302):
                location = auth_res.headers.get("Location") or auth_res.headers.get("location")
                if not location:
                    raise RuntimeError(f"Location header missing from redirect at {current_url}")

                # Resolve relative redirects
                location = urllib.parse.urljoin(current_url, location)

                # Parse request_token from query string
                parsed_url = urllib.parse.urlparse(location)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                request_token_list = query_params.get("request_token")
                if request_token_list:
                    request_token = request_token_list[0]
                    break

                current_url = location
            else:
                # If we get a 200 OK, check if it's the authorize page
                if "connect/authorize" in auth_res.url:
                    logger.info(f"User {self.user_id}: Encountered authorization consent page. Auto-approving...")
                    try:
                        parsed_consent = urllib.parse.urlparse(auth_res.url)
                        consent_params = urllib.parse.parse_qs(parsed_consent.query)
                        approve_res = session.post(
                            "https://kite.zerodha.com/connect/authorize",
                            data={
                                "status": "approve",
                                "client_id": self._api_key,
                                "redirect_params": consent_params.get("redirect_params", [""])[0]
                            },
                            allow_redirects=False
                        )
                        if approve_res.status_code in (301, 302):
                            location = approve_res.headers.get("Location") or approve_res.headers.get("location")
                            location = urllib.parse.urljoin(auth_res.url, location)
                            parsed_url = urllib.parse.urlparse(location)
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            request_token_list = query_params.get("request_token")
                            if request_token_list:
                                request_token = request_token_list[0]
                                break
                            current_url = location
                            continue
                    except Exception as approve_err:
                        logger.error(f"User {self.user_id}: Auto-approval of consent failed: {approve_err}")

                raise RuntimeError(
                    f"Expected redirect (302) from Zerodha login, got status {auth_res.status_code} at {current_url}"
                )

        if not request_token:
            raise RuntimeError("Failed to capture request_token after following redirects.")

        logger.info(f"User {self.user_id}: Captured request_token successfully")

        # 6. Exchange request_token for access_token
        access_token = self.exchange_token(request_token)
        return access_token

    def set_access_token(self, access_token: str):
        """Restore access_token from DB on app startup."""
        if not self._kite:
            raise RuntimeError("KiteService not configured — call configure() first")
        self._kite.set_access_token(access_token)
        self._access_token = access_token
        logger.info(f"User {self.user_id}: Kite access_token restored from DB")

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
            logger.warning(f"User {self.user_id}: Kite token validation failed: {e}")
            self._access_token = None
            return False

    # ── NFO Instrument Cache ─────────────────────────────────────────────────

    def load_instruments(self):
        """
        Fetch all NFO NIFTY option instruments and cache symbol→token.
        Called at 9:00 AM each morning and on startup if authenticated.
        """
        if not self.is_authenticated():
            logger.warning(f"User {self.user_id}: Cannot load instruments — Kite not authenticated")
            return

        logger.info(f"User {self.user_id}: Loading NFO NIFTY instruments from Kite API...")
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
            self._last_api_error = None
            logger.info(f"User {self.user_id}: Loaded {loaded} NIFTY NFO instruments into cache")

        except Exception as e:
            logger.error(f"User {self.user_id}: Failed to load NFO instruments: {e}")
            self._last_api_error = f"Instruments load failed: {str(e)}"

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
        """
        if not self.is_authenticated():
            raise RuntimeError(f"User {self.user_id}: Cannot start KiteTicker — Kite not authenticated")
        if self._ticker_running:
            logger.info(f"User {self.user_id}: KiteTicker already running")
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
                    # Cache Nifty LTP in Redis with a 5s TTL
                    try:
                        get_redis_client().setex("nifty:ltp", 5, str(ltp))
                    except Exception:
                        pass
                    self._last_nifty_tick_time = time.time()
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
            logger.info(f"✅ User {self.user_id}: KiteTicker connected — subscribing to NIFTY 50 spot")
            self._is_connected = True
            self._last_ticker_error = None
            ws.subscribe([NIFTY_SPOT_TOKEN])
            ws.set_mode(ws.MODE_LTP, [NIFTY_SPOT_TOKEN])
            # Re-subscribe to open option positions (e.g. after reconnect)
            if self._subscribed_option_tokens:
                tokens = list(self._subscribed_option_tokens)
                ws.subscribe(tokens)
                ws.set_mode(ws.MODE_LTP, tokens)
                logger.info(f"User {self.user_id}: Re-subscribed {len(tokens)} option tokens on reconnect")

        def on_disconnect(ws, code, reason):
            logger.warning(f"User {self.user_id}: KiteTicker disconnected — code={code} reason={reason}")
            self._is_connected = False
            self._last_ticker_error = f"Disconnected (code={code}): {reason or 'Unknown reason'}"

        def on_error(ws, code, reason):
            logger.error(f"User {self.user_id}: KiteTicker error — code={code} reason={reason}")
            self._last_ticker_error = f"Connection error: {reason or 'Unknown connection error'}"

        def on_reconnect(ws, attempts_count):
            logger.info(f"User {self.user_id}: KiteTicker reconnecting... attempt #{attempts_count}")
            self._last_ticker_error = f"Reconnecting... attempt #{attempts_count}"

        def on_noreconnect(ws):
            logger.error(f"User {self.user_id}: KiteTicker: max reconnect attempts reached — manual restart needed")
            self._ticker_running = False
            self._last_ticker_error = "Failed to connect: Max reconnect attempts reached"

        self._ticker.on_ticks = on_ticks
        self._ticker.on_connect = on_connect
        self._ticker.on_disconnect = on_disconnect
        self._ticker.on_error = on_error
        self._ticker.on_reconnect = on_reconnect
        self._ticker.on_noreconnect = on_noreconnect

        self._ticker.connect(threaded=True)
        self._ticker_running = True
        logger.info(f"User {self.user_id}: KiteTicker background thread started")

    def subscribe_option(self, symbol: str):
        """Subscribe to live tick stream for an option symbol."""
        token = self.get_instrument_token(symbol)
        if token is None:
            logger.warning(f"User {self.user_id}: Cannot subscribe option — token not found: {symbol}")
            return
        self._subscribed_option_tokens.add(token)
        self._token_to_symbol[token] = symbol  # ensure reverse mapping
        if self._ticker and self._is_connected:
            self._ticker.subscribe([token])
            self._ticker.set_mode(self._ticker.MODE_LTP, [token])
            logger.info(f"📊 User {self.user_id}: Subscribed option tick: {symbol} (token={token})")
        else:
            logger.info(f"User {self.user_id}: Queued option subscription (will apply on connect): {symbol}")

    def unsubscribe_option(self, symbol: str):
        """Unsubscribe from option tick stream after exit."""
        token = self.get_instrument_token(symbol)
        if token and token in self._subscribed_option_tokens:
            self._subscribed_option_tokens.discard(token)
            if self._ticker and self._is_connected:
                self._ticker.unsubscribe([token])
            logger.info(f"User {self.user_id}: Unsubscribed option tick: {symbol}")

    def stop_ticker(self):
        """Stop KiteTicker WebSocket."""
        if self._ticker:
            try:
                self._ticker.stop()
            except Exception as e:
                logger.warning(f"User {self.user_id}: Error stopping KiteTicker: {e}")
        self._ticker_running = False
        self._is_connected = False
        logger.info(f"User {self.user_id}: KiteTicker stopped")

    # ── REST LTP (fallback) ──────────────────────────────────────────────────

    def get_ltp_rest(self, symbol: str) -> Optional[Decimal]:
        """Fetch option LTP via REST API with a 2-second rate-limit throttle/cache."""
        if not self.is_authenticated():
            return None

        import time
        now = time.time()
        if symbol in self._rest_ltp_cache:
            last_time, last_val = self._rest_ltp_cache[symbol]
            if now - last_time < 2.0:
                # Return cached value to prevent hitting Zerodha REST rate limits
                return last_val

        try:
            # Pre-set the cache timestamp to avoid concurrent duplicate requests
            self._rest_ltp_cache[symbol] = (now, None)
            resp = self._kite.ltp([f"NFO:{symbol}"])
            ltp = resp.get(f"NFO:{symbol}", {}).get("last_price")
            val = Decimal(str(ltp)) if ltp else None
            self._rest_ltp_cache[symbol] = (now, val)
            self._last_api_error = None
            return val
        except Exception as e:
            logger.error(f"User {self.user_id}: REST LTP fetch failed for {symbol}: {e}")
            self._last_api_error = f"LTP fetch failed: {str(e)}"
            self._rest_ltp_cache[symbol] = (now, None)
            return None

    def get_option_ltp(self, symbol: str) -> Optional[Decimal]:
        """Get option LTP — Redis first (from ticker), REST fallback."""
        try:
            redis = get_redis_client()
            val = redis.get(f"option:ltp:{symbol}")
            if val:
                val_str = val.decode() if isinstance(val, bytes) else str(val)
                return Decimal(val_str)
        except Exception:
            pass
        return self.get_ltp_rest(symbol)

    def get_nifty_spot_ltp(self) -> Optional[Decimal]:
        """Fetch NIFTY spot LTP from Zerodha REST API."""
        if not self.is_authenticated() or not self._kite:
            return None
        try:
            resp = self._kite.ltp(["NSE:NIFTY 50"])
            ltp = resp.get("NSE:NIFTY 50", {}).get("last_price")
            if ltp:
                self._last_api_error = None
                return Decimal(str(ltp))
        except Exception as e:
            logger.warning(f"Failed to fetch NIFTY spot LTP (REST API): {e}")
            self._last_api_error = f"Failed to fetch NIFTY spot LTP: {str(e)}"
        return None

    def get_nifty_prev_close(self) -> Optional[Decimal]:
        """Fetch NIFTY previous close price from Kite REST API."""
        if not self.is_authenticated() or not self._kite:
            return None
        try:
            res = self._kite.quote(["NSE:NIFTY 50"])
            nifty_quote = res.get("NSE:NIFTY 50")
            if nifty_quote:
                ohlc = nifty_quote.get("ohlc")
                if ohlc:
                    close = ohlc.get("close")
                    if close:
                        self._last_api_error = None
                        return Decimal(str(close))
        except Exception as e:
            logger.warning(f"Failed to fetch NIFTY previous close (REST API): {e}")
            self._last_api_error = f"Failed to fetch prev close: {str(e)}"
        return None

    def get_india_vix(self) -> float:
        """Fetch INDIA VIX price from Kite REST API, fallback to 13.5 if unauthenticated or error."""
        if not self.is_authenticated() or not self._kite:
            return 13.5
        try:
            res = self._kite.quote(["NSE:INDIA VIX"])
            vix_quote = res.get("NSE:INDIA VIX")
            if vix_quote:
                last_price = vix_quote.get("last_price")
                if last_price:
                    return float(last_price)
        except Exception as e:
            logger.warning(f"Failed to fetch INDIA VIX (REST API): {e}")
        return 13.5

    def get_option_chain_snapshot(self, current_ltp: float) -> dict:
        """
        Fetch quotes for NIFTY option chain around spot price (ATM ± 300).
        Calculate PCR, Max Pain strike, and CE/PE OI Walls.
        """
        if not self.is_authenticated() or not self._kite:
            return {
                "pcr": 1.0,
                "max_pain": int(round(current_ltp / 50) * 50),
                "ce_wall": int(round((current_ltp + 150) / 50) * 50),
                "pe_wall": int(round((current_ltp - 150) / 50) * 50),
                "spot": current_ltp
            }
        try:
            from app.core.option_selector import get_expiry_date, build_option_symbol
            from app.core.time_rules import today_ist
            
            trade_date = today_ist()
            expiry = get_expiry_date(trade_date)
            
            atm = int(round(current_ltp / 50) * 50)
            strikes = [atm + offset for offset in range(-300, 301, 50)]
            
            symbols = []
            symbol_to_strike_side = {}
            for strike in strikes:
                for side in ("CE", "PE"):
                    sym = build_option_symbol(side, strike, expiry)
                    symbols.append(f"NFO:{sym}")
                    symbol_to_strike_side[f"NFO:{sym}"] = (strike, side)
            
            logger.info(f"User {self.user_id}: Fetching quotes for {len(symbols)} option chain instruments...")
            quotes = self._kite.quote(symbols)
            
            chain = {strike: {"CE": 0, "PE": 0} for strike in strikes}
            total_call_oi = 0
            total_put_oi = 0
            
            ce_wall_strike = atm
            pe_wall_strike = atm
            max_ce_oi = -1
            max_pe_oi = -1
            
            for sym, q in quotes.items():
                oi = q.get("oi", 0)
                strike, side = symbol_to_strike_side.get(sym, (None, None))
                if strike is not None:
                    chain[strike][side] = oi
                    if side == "CE":
                        total_call_oi += oi
                        if oi > max_ce_oi:
                            max_ce_oi = oi
                            ce_wall_strike = strike
                    elif side == "PE":
                        total_put_oi += oi
                        if oi > max_pe_oi:
                            max_pe_oi = oi
                            pe_wall_strike = strike
            
            pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
            
            min_pain = float("inf")
            max_pain_strike = atm
            for k in strikes:
                pain = 0
                for strike, data in chain.items():
                    ce_oi = data["CE"]
                    pe_oi = data["PE"]
                    if k > strike:
                        pain += (k - strike) * ce_oi
                    elif k < strike:
                        pain += (strike - k) * pe_oi
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = k
            
            self._last_api_error = None
            return {
                "pcr": pcr,
                "max_pain": max_pain_strike,
                "ce_wall": ce_wall_strike,
                "pe_wall": pe_wall_strike,
                "spot": current_ltp
            }
        except Exception as e:
            logger.error(f"User {self.user_id}: Failed to compute option chain snapshot: {e}")
            self._last_api_error = f"Option chain snapshot failed: {str(e)}"
            return {
                "pcr": 1.0,
                "max_pain": int(round(current_ltp / 50) * 50),
                "ce_wall": int(round((current_ltp + 150) / 50) * 50),
                "pe_wall": int(round((current_ltp - 150) / 50) * 50),
                "spot": current_ltp
            }

    # ── Status ───────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        last_seconds = None
        if self._last_nifty_tick_time:
            last_seconds = int(time.time() - self._last_nifty_tick_time)

        # Trigger background margin update if authenticated and cache expired
        now = time.time()
        if self.is_authenticated() and (self._available_margin is None or now - self._last_margin_fetch_time > 300):
            self._last_margin_fetch_time = now
            import threading
            threading.Thread(target=self._bg_fetch_margin, daemon=True).start()

        return {
            "authenticated": self.is_authenticated(),
            "ticker_connected": self._is_connected,
            "ticker_running": self._ticker_running,
            "instruments_loaded": self._instruments_loaded,
            "subscribed_options": len(self._subscribed_option_tokens),
            "api_key_masked": mask_key(self._api_key) if self._api_key else None,
            "last_nifty_tick_seconds_ago": last_seconds,
            "last_api_error": self._last_api_error,
            "last_ticker_error": self._last_ticker_error,
            "available_margin": self._available_margin,
        }

    def _bg_fetch_margin(self):
        try:
            if self.is_authenticated() and self._kite:
                margins = self._kite.margins()
                self._available_margin = float(margins.get("equity", {}).get("net", 0.0))
        except Exception as e:
            logger.warning(f"User {self.user_id}: Failed to fetch margin in background: {e}")

    def clear_credentials(self):
        """Remove access token (called on logout)."""
        self._access_token = None
        if self._kite:
            try:
                self._kite.set_access_token(None)
            except Exception:
                pass
        self.stop_ticker()


# Global user instance cache
_user_instances: dict[int, KiteService] = {}


def get_user_kite_service(user_id: int) -> KiteService:
    """Get or create KiteService instance for a specific user."""
    if user_id not in _user_instances:
        _user_instances[user_id] = KiteService(user_id)
    return _user_instances[user_id]


# Global singleton (defaults to user_id=1 for backward compatibility/tests)
kite_service = get_user_kite_service(1)