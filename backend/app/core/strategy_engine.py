"""
Strategy Engine — The Core Pyramid Logic
Orchestrates CE and PE state machines independently.
Processes each NIFTY tick and triggers entries/exits per CLAUDE.md rules.
Multi-User version: instantiated per user_id.
"""

import asyncio
from decimal import Decimal
from typing import Optional, Callable
from sqlalchemy.orm import Session
from loguru import logger

from app.core.state_machine import StateMachine, State
from app.core.time_rules import is_entry_allowed, should_squareoff, today_ist
from app.core.option_selector import get_option_details, estimate_option_price
from app.core.order_manager import OrderManager
from app.db.database import SessionLocal, get_redis_client
from app.config import settings


class StrategyEngine:
    """
    User-specific strategy engine.
    Processes NIFTY ticks for a single user.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.is_running: bool = False
        self.last_nifty_price: Optional[Decimal] = None
        self.last_entry_time: dict[str, float] = {"CE": 0.0, "PE": 0.0}

        # Independent state machines per CLAUDE.md
        self.ce = StateMachine(side="CE")
        self.pe = StateMachine(side="PE")

        # Config (loaded from DB)
        self.config: Optional[dict] = None

        # Option LTP cache (updated by market data feed)
        self._option_ltp: dict[str, Decimal] = {}  # symbol → ltp
        self.nifty_prev_close: Optional[Decimal] = Decimal("23150.00")

        # Order manager (initialized with user_id)
        self.order_manager = OrderManager(user_id=self.user_id, kite_service=None)

        # User-specific mock data feed
        from app.services.mock_feed import MockDataFeed
        self.mock_feed = MockDataFeed(engine=self)

        # WebSocket broadcaster (broadcasts only to this user)
        self.broadcast_fn: Optional[Callable] = None

        # Mock feed flag
        self.mock_mode: bool = settings.PAPER_TRADE

        logger.info(f"StrategyEngine initialized for User {user_id}")

    def load_config(self, config: dict):
        """Load strategy configuration from DB."""
        self.config = config
        lot_size = config.get("lot_size", 75)
        target = Decimal(str(config.get("target_points", 20)))
        sl = Decimal(str(config.get("sl_points", 10)))

        # Load paper trade mode dynamically from configuration
        self.mock_mode = config.get("paper_trade", True)
        self.order_manager.paper_trade = self.mock_mode

        # Apply config to both state machines
        self.ce.lot_size = lot_size
        self.ce.target_points = target
        self.ce.sl_points = sl
        self.pe.lot_size = lot_size
        self.pe.target_points = target
        self.pe.sl_points = sl

        logger.info(
            f"User {self.user_id} config loaded: R1={config['r1']} R2={config['r2']} R3={config['r3']} "
            f"| S1={config['s1']} S2={config['s2']} S3={config['s3']} "
            f"| lot_size={lot_size} | target={target} | sl={sl} | paper_trade={self.mock_mode}"
        )

    def daily_reset(self):
        """Reset state machines at start of each trading day (9:00 AM)."""
        self.ce.reset_daily()
        self.pe.reset_daily()
        self._option_ltp.clear()
        self.last_entry_time = {"CE": 0.0, "PE": 0.0}
        logger.info(f"User {self.user_id}: Daily reset complete — state machines reset")

    def start(self):
        self.is_running = True
        logger.info(f"User {self.user_id}: Strategy engine STARTED")
        try:
            # Notifications are user-specific, but can fail gracefully if not configured
            from app.services.notification import NotificationService
            # We skip global notifications to avoid conflicts
        except Exception:
            pass

    def stop(self):
        self.is_running = False
        logger.info(f"User {self.user_id}: Strategy engine STOPPED")

    def update_option_ltp(self, symbol: str, ltp: Decimal):
        """Called by market data feed when option price updates."""
        self._option_ltp[symbol] = ltp

    def get_option_ltp(self, symbol: str) -> Optional[Decimal]:
        if not symbol:
            return None
        # Try real Kite service first if authenticated (allows live-data paper trading)
        try:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if kite_service.is_authenticated():
                kite_ltp = kite_service.get_option_ltp(symbol)
                if kite_ltp is not None:
                    return kite_ltp
        except Exception as e:
            logger.warning(f"Error fetching live option LTP from Kite: {e}")
        return self._option_ltp.get(symbol)

    async def on_option_tick(self, symbol: str, ltp: Decimal):
        """Callback from KiteTicker for option price updates."""
        self._option_ltp[symbol] = ltp

    # ── Main Tick Processor ──────────────────────────────────────────────────

    async def on_nifty_tick(self, nifty_ltp: Decimal):
        """
        Called on every NIFTY price tick.
        Processes CE and PE independently.
        """
        try:
            get_redis_client().setex("nifty:ltp", 5, str(nifty_ltp))
        except Exception:
            pass

        if not self.is_running or not self.config:
            self.last_nifty_price = nifty_ltp
            return

        # Check squareoff first (highest priority)
        if should_squareoff(squareoff_time_str=self.config.get("squareoff_time", "11:30")):
            self.last_nifty_price = nifty_ltp
            await self._force_squareoff()
            return

        prev_nifty = self.last_nifty_price

        # Process both sides independently
        await asyncio.gather(
            self._process_side("PE", nifty_ltp, prev_nifty),
            self._process_side("CE", nifty_ltp, prev_nifty),
            return_exceptions=True,
        )

        self.last_nifty_price = nifty_ltp

        # Broadcast updated status to frontend
        await self._broadcast_status(nifty_ltp)

    # ── Side Processing ──────────────────────────────────────────────────────

    async def _process_side(self, side: str, nifty_ltp: Decimal, prev_nifty: Optional[Decimal]):
        """Process a single side (CE or PE) for a given NIFTY tick."""
        sm: StateMachine = self.ce if side == "CE" else self.pe

        try:
            # Check target/SL for open positions first
            await self._check_target_sl(sm, nifty_ltp)

            # Check for new level entries
            if sm.state in (State.IDLE, State.L1_ENTERED, State.L2_ENTERED):
                await self._check_level_entry(sm, side, nifty_ltp, prev_nifty)

        except Exception as e:
            logger.error(f"User {self.user_id} [{side}] Error processing tick: {e}", exc_info=True)
            await self._broadcast_error(side, str(e))

    async def _check_level_entry(self, sm: StateMachine, side: str, nifty_ltp: Decimal, prev_nifty: Optional[Decimal]):
        """Check if NIFTY has hit a trigger level and entry is warranted."""
        if not is_entry_allowed(squareoff_time_str=self.config.get("squareoff_time", "11:30")):
            return

        cfg = self.config
        r1, r2, r3 = Decimal(str(cfg["r1"])), Decimal(str(cfg["r2"])), Decimal(str(cfg["r3"]))
        s1, s2, s3 = Decimal(str(cfg["s1"])), Decimal(str(cfg["s2"])), Decimal(str(cfg["s3"]))

        if side == "PE":
            await self._handle_pe_levels(sm, nifty_ltp, prev_nifty, r1, r2, r3)
        else:
            await self._handle_ce_levels(sm, nifty_ltp, prev_nifty, s1, s2, s3)

    async def _handle_pe_levels(self, sm: StateMachine, ltp: Decimal, prev_nifty: Optional[Decimal],
                                  r1: Decimal, r2: Decimal, r3: Decimal):
        """PE: trigger when NIFTY hits or crosses resistance levels from below."""
        import time
        cooldown_elapsed = time.time() - self.last_entry_time.get("PE", 0.0) >= 60

        if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty < r1 and ltp >= r1:
            await self._execute_entry(sm, "PE", "L1", ltp, r1)

        elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r2 and ltp >= r2:
            await self._execute_entry(sm, "PE", "L2", ltp, r2)

        elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r3 and ltp >= r3:
            await self._execute_entry(sm, "PE", "L3", ltp, r3)

    async def _handle_ce_levels(self, sm: StateMachine, ltp: Decimal, prev_nifty: Optional[Decimal],
                                  s1: Decimal, s2: Decimal, s3: Decimal):
        """CE: trigger when NIFTY hits or crosses support levels from above."""
        import time
        cooldown_elapsed = time.time() - self.last_entry_time.get("CE", 0.0) >= 60

        if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty > s1 and ltp <= s1:
            await self._execute_entry(sm, "CE", "L1", ltp, s1)

        elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s2 and ltp <= s2:
            await self._execute_entry(sm, "CE", "L2", ltp, s2)

        elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s3 and ltp <= s3:
            await self._execute_entry(sm, "CE", "L3", ltp, s3)

    async def _execute_entry(self, sm: StateMachine, side: str, level: str,
                               nifty_ltp: Decimal, trigger_level: Decimal):
        """Execute an entry at the given level."""
        import time
        self.last_entry_time[side] = time.time()
        with SessionLocal() as db:
            # At L1: resolve option symbol
            if level == "L1":
                opt = get_option_details(side, nifty_ltp)
                instrument = opt["symbol"]
                strike = opt["strike"]
                expiry = opt["expiry"]
                mock_ltp = self._get_mock_option_ltp(instrument)

                order = self.order_manager.place_buy_order(
                    db=db, side=side, level=level,
                    instrument=instrument, strike=strike, expiry=expiry,
                    lots=1, lot_size=sm.lot_size,
                    trigger_nifty=nifty_ltp, mock_ltp=mock_ltp,
                )
                sm.enter_level1(instrument, strike, expiry, order["fill_price"])

            elif level == "L2":
                instrument = sm.locked_instrument
                mock_ltp = self._get_mock_option_ltp(instrument)
                order = self.order_manager.place_buy_order(
                    db=db, side=side, level=level,
                    instrument=instrument, strike=sm.locked_strike, expiry=sm.locked_expiry,
                    lots=1, lot_size=sm.lot_size,
                    trigger_nifty=nifty_ltp, mock_ltp=mock_ltp,
                )
                sm.enter_level2(order["fill_price"])

            elif level == "L3":
                instrument = sm.locked_instrument
                mock_ltp = self._get_mock_option_ltp(instrument)
                order = self.order_manager.place_buy_order(
                    db=db, side=side, level=level,
                    instrument=instrument, strike=sm.locked_strike, expiry=sm.locked_expiry,
                    lots=1, lot_size=sm.lot_size,
                    trigger_nifty=nifty_ltp, mock_ltp=mock_ltp,
                )
                sm.enter_level3(order["fill_price"])

        # Subscribe to option tick stream (Phase 2: live prices for target/SL)
        self._subscribe_option(sm.locked_instrument)

        # Broadcast trade event to frontend
        await self._broadcast_trade_event(side, level, "ENTRY", sm.get_status())

        # Fire AI analysis AFTER order — non-blocking
        asyncio.create_task(self._notify_ai("ENTRY", side, level, nifty_ltp))

    async def _check_target_sl(self, sm: StateMachine, nifty_ltp: Decimal):
        """Check if open position has hit target or SL."""
        if sm.state == State.IDLE or sm.locked_instrument is None:
            return

        option_ltp = self.get_option_ltp(sm.locked_instrument)
        if option_ltp is None:
            return

        if sm.check_target(option_ltp):
            await self._execute_exit(sm, option_ltp, "TARGET", nifty_ltp)
        elif sm.check_sl(option_ltp):
            await self._execute_exit(sm, option_ltp, "SL", nifty_ltp)

    async def _execute_exit(self, sm: StateMachine, exit_price: Decimal,
                              reason: str, nifty_ltp: Decimal):
        """Execute full position exit."""
        with SessionLocal() as db:
            self.order_manager.place_exit_order(
                db=db,
                side=sm.side,
                instrument=sm.locked_instrument,
                strike=sm.locked_strike,
                qty=sm.total_qty,
                reason=reason,
                entry_avg_price=sm.entry_avg_price,
                mock_ltp=exit_price,
                trigger_nifty=nifty_ltp,
                lot_size=sm.lot_size,
            )

        # Unsubscribe from option ticks — position closed
        self._unsubscribe_option(sm.locked_instrument)

        exit_result = sm.exit_position(exit_price, reason)
        await self._broadcast_trade_event(sm.side, "EXIT", reason, exit_result)

        asyncio.create_task(self._notify_ai("EXIT", sm.side, reason, nifty_ltp))

    async def _force_squareoff(self):
        """Force close all open positions at configured squareoff time."""
        sq_time_str = self.config.get("squareoff_time", "11:30") if self.config else "11:30"
        for sm in (self.ce, self.pe):
            if sm.state not in (State.IDLE, State.BLOCKED):
                option_ltp = self.get_option_ltp(sm.locked_instrument) or sm.entry_avg_price
                logger.warning(f"User {self.user_id} [{sm.side}] FORCE SQUAREOFF at {sq_time_str}")
                await self._execute_exit(sm, option_ltp, "SQUAREOFF", Decimal("0"))

        self.stop()

    # ── Kite Option Subscription ─────────────────────────────────────────────

    def _subscribe_option(self, symbol: Optional[str]):
        """Subscribe to live option ticks after entry (Phase 2)."""
        if not symbol:
            return
        try:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if kite_service.is_authenticated() and kite_service._ticker_running:
                kite_service.subscribe_option(symbol)
        except Exception as e:
            logger.warning(f"Option subscribe failed (non-critical): {e}")

    def _unsubscribe_option(self, symbol: Optional[str]):
        """Unsubscribe from option ticks after exit (Phase 2)."""
        if not symbol:
            return
        try:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if kite_service.is_authenticated():
                kite_service.unsubscribe_option(symbol)
        except Exception as e:
            logger.warning(f"Option unsubscribe failed (non-critical): {e}")

    # ── Mock Option LTP ──────────────────────────────────────────────────────

    def _get_mock_option_ltp(self, symbol: str) -> Decimal:
        """Return cached option LTP, or generate a mock price for paper trading."""
        ltp = self.get_option_ltp(symbol)
        if ltp is not None:
            return ltp
        if self.last_nifty_price:
            return estimate_option_price(symbol, self.last_nifty_price)
        return Decimal("100.00")

    # ── Broadcasting ─────────────────────────────────────────────────────────

    async def _broadcast_status(self, nifty_ltp: Decimal):
        if not self.broadcast_fn:
            return
        from app.services.kite_service import get_user_kite_service
        ks = get_user_kite_service(self.user_id)

        if not self.mock_mode and (not self.nifty_prev_close or self.nifty_prev_close == Decimal("23150.00")):
            try:
                live_prev_close = ks.get_nifty_prev_close()
                if live_prev_close:
                    self.nifty_prev_close = live_prev_close
            except Exception as e:
                logger.warning(f"Error fetching live NIFTY previous close: {e}")

        status = {
            "type": "strategy_status",
            "user_id": self.user_id,
            "data": {
                "nifty_ltp": float(nifty_ltp),
                "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
                "is_running": self.is_running,
                "paper_trade": self.mock_mode,
                "entries_allowed": is_entry_allowed(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
                "squareoff_triggered": should_squareoff(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
                "ce": self.ce.get_status(self.get_option_ltp(self.ce.locked_instrument or "")),
                "pe": self.pe.get_status(self.get_option_ltp(self.pe.locked_instrument or "")),
                "health": ks.get_status(),
            },
        }
        await self.broadcast_fn(self.user_id, status)

    async def _broadcast_trade_event(self, side: str, level: str, action: str, details: dict):
        if not self.broadcast_fn:
            return
        mapped_level = level
        if level in ("L1", "L2", "L3"):
            mapped_level = level.replace("L", "S" if side == "CE" else "R")
        await self.broadcast_fn(self.user_id, {
            "type": "trade_event",
            "user_id": self.user_id,
            "data": {"side": side, "level": mapped_level, "action": action, **details},
        })

    async def _broadcast_error(self, side: str, message: str):
        if not self.broadcast_fn:
            return
        await self.broadcast_fn(self.user_id, {
            "type": "error",
            "user_id": self.user_id,
            "data": {"side": side, "message": message}
        })

    async def _notify_ai(self, event: str, side: str, level: str, nifty_ltp: Decimal):
        """Fire-and-forget AI analysis. Never blocks strategy execution."""
        try:
            from app.services.ai_service import ai_service
            if ai_service.is_enabled():
                suggestion = await ai_service.analyze(event, side, level, float(nifty_ltp))
                if suggestion and self.broadcast_fn:
                    await self.broadcast_fn(self.user_id, {
                        "type": "ai_suggestion",
                        "user_id": self.user_id,
                        "data": {"suggestion": suggestion, "event": event, "side": side},
                    })
        except Exception as e:
            logger.warning(f"AI analysis failed (non-critical): {e}")

    # ── Public status ─────────────────────────────────────────────────────────

    def get_full_status(self) -> dict:
        nifty_ltp_str = get_redis_client().get("nifty:ltp")
        nifty_ltp = Decimal(nifty_ltp_str) if nifty_ltp_str else None

        from app.services.kite_service import get_user_kite_service
        ks = get_user_kite_service(self.user_id)

        if not self.mock_mode and (not self.nifty_prev_close or self.nifty_prev_close == Decimal("23150.00")):
            try:
                live_prev_close = ks.get_nifty_prev_close()
                if live_prev_close:
                    self.nifty_prev_close = live_prev_close
            except Exception:
                pass

        return {
            "is_running": self.is_running,
            "paper_trade": self.mock_mode,
            "nifty_ltp": float(nifty_ltp) if nifty_ltp else None,
            "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
            "entries_allowed": is_entry_allowed(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
            "squareoff_triggered": should_squareoff(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
            "ce": self.ce.get_status(self.get_option_ltp(self.ce.locked_instrument or "")),
            "pe": self.pe.get_status(self.get_option_ltp(self.pe.locked_instrument or "")),
            "health": ks.get_status(),
        }
