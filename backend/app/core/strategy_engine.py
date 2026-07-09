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
        self.squareoff_triggered: bool = False
        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.last_nifty_price: Optional[Decimal] = None
        self.last_entry_time: dict[str, float] = {"CE": 0.0, "PE": 0.0}
        self._is_processing_tick: bool = False
        self._processing_option_symbols: set[str] = set()

        # Independent state machines per CLAUDE.md
        self.ce = StateMachine(side="CE")
        self.pe = StateMachine(side="PE")

        # Post-exit target tracking trades (symbol -> list of trade IDs)
        self.post_exit_trades: dict[str, list[int]] = {}

        # Config (loaded from DB)
        self.config: Optional[dict] = None

        # Option LTP cache (updated by market data feed)
        self._option_ltp: dict[str, Decimal] = {}  # symbol → ltp
        self.nifty_prev_close: Optional[Decimal] = Decimal("24175.70")

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
        self.post_exit_trades.clear()
        self.last_entry_time = {"CE": 0.0, "PE": 0.0}
        self.started_at = None
        self.stopped_at = None
        self.squareoff_triggered = False
        self._is_processing_tick = False
        self._processing_option_symbols.clear()
        logger.info(f"User {self.user_id}: Daily reset complete — state machines reset")

    def start(self):
        self.is_running = True
        self.squareoff_triggered = False
        from datetime import datetime
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        self.started_at = datetime.now(ist).strftime("%I:%M:%S %p")
        self.stopped_at = None
        logger.info(f"User {self.user_id}: Strategy engine STARTED at {self.started_at}")
        
        # Load any existing target trades for today to continue post-exit high/low tracking
        self.load_post_exit_trades()

        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_engine_started(paper_trade=self.mock_mode)
        except Exception as e:
            logger.warning(f"Failed to send engine started alert: {e}")

    def load_post_exit_trades(self):
        """Load today's TARGET trades to continue post-exit high/low tracking and restore blocked levels after restarts."""
        self.post_exit_trades = {}
        try:
            with SessionLocal() as db:
                from app.models.models import Trade
                from app.core.time_rules import today_ist
                target_date = today_ist()

                # Fetch all today's trades for this user
                all_trades = db.query(Trade).filter(
                    Trade.user_id == self.user_id
                ).all()

                # 1. Restore post-exit tracking for TARGET trades
                target_trades = [
                    t for t in all_trades
                    if t.trade_date == target_date and t.status == "TARGET"
                ]
                for trade in target_trades:
                    symbol = trade.instrument
                    if symbol not in self.post_exit_trades:
                        self.post_exit_trades[symbol] = []
                    if trade.id not in self.post_exit_trades[symbol]:
                        self.post_exit_trades[symbol].append(trade.id)
                    if symbol not in self._option_ltp:
                        self._option_ltp[symbol] = Decimal(str(trade.avg_price)) if trade.avg_price else Decimal("100.00")
                    # Subscribe to live ticks for this instrument
                    self._subscribe_option(symbol)

                # 2. Restore blocked levels for state machines (Rule 2.3 Point 5)
                # Find all BUY trades today that have been exited (status is not OPEN)
                exited_buys = [
                    t for t in all_trades
                    if t.trade_date == target_date and t.action == "BUY" and t.status != "OPEN"
                ]
                for trade in exited_buys:
                    # Map S1/R1 -> L1, S2/R2 -> L2, S3/R3 -> L3
                    lvl_char = trade.level[1] if trade.level and len(trade.level) > 1 else None
                    if lvl_char in ("1", "2", "3"):
                        mapped_lvl = f"L{lvl_char}"
                        if trade.side == "CE":
                            self.ce.blocked_levels.add(mapped_lvl)
                        elif trade.side == "PE":
                            self.pe.blocked_levels.add(mapped_lvl)

            logger.info(
                f"User {self.user_id}: Loaded {len(self.post_exit_trades)} instruments for post-exit tracking | "
                f"Restored blocked levels: CE={self.ce.blocked_levels}, PE={self.pe.blocked_levels}"
            )
        except Exception as e:
            logger.warning(f"Error loading post-exit trades & blocked levels: {e}")

    def stop(self):
        self.is_running = False
        from datetime import datetime
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        self.stopped_at = datetime.now(ist).strftime("%I:%M:%S %p")
        logger.info(f"User {self.user_id}: Strategy engine STOPPED at {self.stopped_at}")
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_engine_stopped()
        except Exception as e:
            logger.warning(f"Failed to send engine stopped alert: {e}")

    def update_option_ltp(self, symbol: str, ltp: Decimal):
        """Called by market data feed when option price updates."""
        self._option_ltp[symbol] = ltp
        if self.is_running:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._process_post_exit_tick(symbol, ltp))
            except RuntimeError:
                pass

    def get_option_ltp(self, symbol: str) -> Optional[Decimal]:
        if not symbol:
            return None
        # If in paper trade mode and we have a cached/simulated LTP, prioritize it
        if self.mock_mode and symbol in self._option_ltp:
            return self._option_ltp[symbol]
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
        
        # Track active high/low during position lifetime
        for sm in [self.ce, self.pe]:
            if sm.state != State.IDLE and sm.locked_instrument == symbol:
                import pytz
                from datetime import datetime
                now = datetime.now(pytz.utc)
                if sm.active_high is None or ltp > sm.active_high:
                    sm.active_high = ltp
                    sm.active_high_time = now
                if sm.active_low is None or ltp < sm.active_low:
                    sm.active_low = ltp
                    sm.active_low_time = now
                    
        await self._process_post_exit_tick(symbol, ltp)

    async def _process_post_exit_tick(self, symbol: str, ltp: Decimal):
        """Check and update post-exit high/low for completed target trades on this instrument."""
        if not hasattr(self, "post_exit_trades") or not self.post_exit_trades:
            return
        
        trade_ids = self.post_exit_trades.get(symbol)
        if not trade_ids:
            return

        if not hasattr(self, "_processing_option_symbols"):
            self._processing_option_symbols = set()

        if symbol in self._processing_option_symbols:
            return
        self._processing_option_symbols.add(symbol)
        try:
            import pytz
            from datetime import datetime
            now = datetime.now(pytz.utc)

            updated_any = False
            with SessionLocal() as db:
                from app.models.models import Trade
                trades = db.query(Trade).filter(Trade.id.in_(trade_ids)).all()
                for trade in trades:
                    updated_trade = False
                    ltp_dec = Decimal(str(ltp))
                    if trade.post_exit_high is None or ltp_dec > Decimal(str(trade.post_exit_high)):
                        trade.post_exit_high = ltp_dec
                        trade.post_exit_high_time = now
                        updated_trade = True
                    if trade.post_exit_low is None or ltp_dec < Decimal(str(trade.post_exit_low)):
                        trade.post_exit_low = ltp_dec
                        trade.post_exit_low_time = now
                        updated_trade = True
                    
                    if updated_trade:
                        updated_any = True
                
                if updated_any:
                    db.commit()
            
            if updated_any:
                await self._broadcast_trade_event(
                    side="CE" if "CE" in symbol else "PE",
                    level="EXIT",
                    action="POST_EXIT_UPDATE",
                    details={"instrument": symbol}
                )
        except Exception as e:
            logger.warning(f"Error in _process_post_exit_tick: {e}")
        finally:
            self._processing_option_symbols.discard(symbol)

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

        # In paper trade mode, estimate and update option prices for locked instruments ONLY if live ticker is not running
        if self.mock_mode:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if not (kite_service.is_authenticated() and kite_service._ticker_running):
                for sm in [self.ce, self.pe]:
                    if sm.locked_instrument:
                        est_price = estimate_option_price(sm.locked_instrument, nifty_ltp)
                        self._option_ltp[sm.locked_instrument] = est_price
                        # Update active range tracking during simulated ticks
                        if sm.state != State.IDLE:
                            import pytz
                            from datetime import datetime
                            now = datetime.now(pytz.utc)
                            if sm.active_high is None or est_price > sm.active_high:
                                sm.active_high = est_price
                                sm.active_high_time = now
                            if sm.active_low is None or est_price < sm.active_low:
                                sm.active_low = est_price
                                sm.active_low_time = now

        if not self.is_running or not self.config:
            self.last_nifty_price = nifty_ltp
            return

        if self._is_processing_tick:
            logger.debug(f"User {self.user_id}: Tick ignored — engine busy processing previous tick")
            return

        self._is_processing_tick = True
        try:
            # Check squareoff first (highest priority)
            if should_squareoff(squareoff_time_str=self.config.get("squareoff_time", "11:30")):
                self.last_nifty_price = nifty_ltp
                if not self.squareoff_triggered:
                    self.squareoff_triggered = True
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
        finally:
            self._is_processing_tick = False

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

    async def _handle_pe_levels(
        self, sm: StateMachine, ltp: Decimal, prev_nifty: Optional[Decimal],
        r1: Decimal, r2: Decimal, r3: Decimal
    ):
        """PE: trigger when NIFTY hits or crosses resistance levels from below."""
        import time
        cooldown_elapsed = time.time() - self.last_entry_time.get("PE", 0.0) >= 60

        if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty < r1 and ltp >= r1:
            await self._execute_entry(sm, "PE", "L1", ltp, r1)

        elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r2 and ltp >= r2:
            await self._execute_entry(sm, "PE", "L2", ltp, r2)

        elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r3 and ltp >= r3:
            await self._execute_entry(sm, "PE", "L3", ltp, r3)

    async def _handle_ce_levels(
        self, sm: StateMachine, ltp: Decimal, prev_nifty: Optional[Decimal],
        s1: Decimal, s2: Decimal, s3: Decimal
    ):
        """CE: trigger when NIFTY hits or crosses support levels from above."""
        import time
        cooldown_elapsed = time.time() - self.last_entry_time.get("CE", 0.0) >= 60

        if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty > s1 and ltp <= s1:
            await self._execute_entry(sm, "CE", "L1", ltp, s1)

        elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s2 and ltp <= s2:
            await self._execute_entry(sm, "CE", "L2", ltp, s2)

        elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s3 and ltp <= s3:
            await self._execute_entry(sm, "CE", "L3", ltp, s3)

    async def _execute_entry(
        self, sm: StateMachine, side: str, level: str,
        nifty_ltp: Decimal, trigger_level: Decimal
    ):
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
                # Get the option LTP (falls back to estimate_option_price if live feed is down/not authenticated)
                mock_ltp = self._get_mock_option_ltp(instrument)
                if self.mock_mode:
                    self._option_ltp[instrument] = mock_ltp

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

        # Send Telegram / WhatsApp alerts
        try:
            def safe_decimal(v) -> Decimal:
                if v is None:
                    return Decimal("0")
                s = str(v).strip()
                if s.lower() in ("none", "null", "nan", ""):
                    return Decimal("0")
                try:
                    return Decimal(s)
                except Exception:
                    return Decimal("0")

            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_trade_entry(
                side=side,
                level=level,
                instrument=sm.locked_instrument,
                lots=1,
                fill_price=safe_decimal(order.get("fill_price")),
                nifty_ltp=safe_decimal(nifty_ltp),
            )
        except Exception as e:
            logger.warning(f"Failed to send trade entry alert: {e}")

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

    async def _execute_exit(
        self, sm: StateMachine, exit_price: Decimal,
        reason: str, nifty_ltp: Decimal
    ):
        """Execute full position exit."""
        instrument = sm.locked_instrument
        with SessionLocal() as db:
            order_res = self.order_manager.place_exit_order(
                db=db,
                side=sm.side,
                instrument=instrument,
                strike=sm.locked_strike,
                qty=sm.total_qty,
                reason=reason,
                entry_avg_price=sm.entry_avg_price,
                mock_ltp=exit_price,
                trigger_nifty=nifty_ltp,
                lot_size=sm.lot_size,
                active_high=sm.active_high,
                active_low=sm.active_low,
                active_high_time=sm.active_high_time,
                active_low_time=sm.active_low_time,
            )

        # Unsubscribe from option ticks — position closed
        # Unless it hit TARGET, in which case we continue tracking post-exit high/low
        if reason == "TARGET":
            updated_trade_ids = order_res.get("updated_trade_ids", [])
            if instrument:
                if instrument not in self.post_exit_trades:
                    self.post_exit_trades[instrument] = []
                for tid in updated_trade_ids:
                    if tid not in self.post_exit_trades[instrument]:
                        self.post_exit_trades[instrument].append(tid)
        else:
            self._unsubscribe_option(instrument)

        exit_result = sm.exit_position(exit_price, reason)
        await self._broadcast_trade_event(sm.side, "EXIT", reason, exit_result)

        # Send Telegram / WhatsApp alerts
        try:
            def safe_decimal(v) -> Decimal:
                if v is None:
                    return Decimal("0")
                s = str(v).strip()
                if s.lower() in ("none", "null", "nan", ""):
                    return Decimal("0")
                try:
                    return Decimal(s)
                except Exception:
                    return Decimal("0")

            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            
            instrument_val = exit_result.get("instrument")
            lots_val = exit_result.get("lots", 0)
            entry_avg_val = exit_result.get("entry_avg_price")
            pnl_rupees_val = exit_result.get("pnl_rupees", Decimal("0"))
            
            if reason == "TARGET":
                ns.notify_target_hit(
                    side=sm.side,
                    instrument=instrument_val,
                    lots=lots_val,
                    exit_price=safe_decimal(exit_price),
                    entry_avg=safe_decimal(entry_avg_val),
                    pnl_rupees=safe_decimal(pnl_rupees_val),
                )
            elif reason == "SL":
                ns.notify_sl_hit(
                    side=sm.side,
                    instrument=instrument_val,
                    lots=lots_val,
                    exit_price=safe_decimal(exit_price),
                    entry_avg=safe_decimal(entry_avg_val),
                    pnl_rupees=safe_decimal(pnl_rupees_val),
                )
        except Exception as e:
            logger.warning(f"Failed to send trade exit alert: {e}")

        asyncio.create_task(self._notify_ai("EXIT", sm.side, reason, nifty_ltp))

    async def _force_squareoff(self):
        """Force close all open positions at configured squareoff time."""
        self.squareoff_triggered = True
        self.is_running = False
        sq_time_str = self.config.get("squareoff_time", "11:30") if self.config else "11:30"
        
        # 1. Close any active positions
        for sm in (self.ce, self.pe):
            if sm.state not in (State.IDLE, State.BLOCKED):
                option_ltp = self.get_option_ltp(sm.locked_instrument) or sm.entry_avg_price
                logger.warning(f"User {self.user_id} [{sm.side}] FORCE SQUAREOFF at {sq_time_str}")
                await self._execute_exit(sm, option_ltp or Decimal("0"), "SQUAREOFF", Decimal("0"))

        # 2. Query today's completed trades from database to send the correct total daily P&L
        ce_pnl = Decimal("0")
        pe_pnl = Decimal("0")
        try:
            from app.models.models import Trade
            target_date = today_ist()
            with SessionLocal() as db:
                all_trades = (
                    db.query(Trade)
                    .filter(Trade.user_id == self.user_id)
                    .all()
                )
                trades = [
                    t for t in all_trades
                    if t.trade_date == target_date and t.action == "EXIT"
                ]
                logger.info(f"User {self.user_id} squareoff P&L query: fetched {len(all_trades)} total trades, found {len(trades)} exits for {target_date}")
                for t in trades:
                    pnl_val = Decimal(str(t.pnl or 0))
                    if t.side == "CE":
                        ce_pnl += pnl_val
                    elif t.side == "PE":
                        pe_pnl += pnl_val
        except Exception as db_err:
            logger.error(f"Failed to query today's trades for squareoff P&L: {db_err}")

        # Send Telegram / WhatsApp alerts
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_squareoff(ce_pnl, pe_pnl, sq_time_str)
        except Exception as e:
            logger.warning(f"Failed to send squareoff alert: {e}")

        self.stop()

    async def emergency_exit(self) -> dict:
        """Force close all open positions immediately and stop the engine."""
        self.is_running = False
        exited_count = 0
        total_pnl = Decimal("0")

        for sm in (self.ce, self.pe):
            if sm.state not in (State.IDLE, State.BLOCKED):
                option_ltp = self.get_option_ltp(sm.locked_instrument) or sm.entry_avg_price or Decimal("0")
                logger.warning(f"User {self.user_id} [{sm.side}] EMERGENCY EXIT triggered")
                exit_res = await self._execute_exit(sm, option_ltp, "MANUAL", Decimal("0"))
                exited_count += 1
                if exit_res:
                    total_pnl += Decimal(str(exit_res.get("pnl_rupees", "0")))

        self.stop()
        return {
            "status": "emergency_exited",
            "exited_count": exited_count,
            "pnl_rupees": float(total_pnl)
        }

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

        if ks.is_authenticated() and (not self.nifty_prev_close or self.nifty_prev_close == Decimal("24175.70")):
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
        nifty_ltp = Decimal(nifty_ltp_str) if nifty_ltp_str else self.last_nifty_price

        from app.services.kite_service import get_user_kite_service
        ks = get_user_kite_service(self.user_id)

        if ks.is_authenticated() and (not self.nifty_prev_close or self.nifty_prev_close == Decimal("24175.70")):
            try:
                live_prev_close = ks.get_nifty_prev_close()
                if live_prev_close:
                    self.nifty_prev_close = live_prev_close
            except Exception:
                pass

        return {
            "is_running": self.is_running,
            "paper_trade": self.mock_mode,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "nifty_ltp": float(nifty_ltp) if nifty_ltp else None,
            "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
            "entries_allowed": is_entry_allowed(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
            "squareoff_triggered": should_squareoff(squareoff_time_str=self.config.get("squareoff_time", "11:30") if self.config else "11:30"),
            "ce": self.ce.get_status(self.get_option_ltp(self.ce.locked_instrument or "")),
            "pe": self.pe.get_status(self.get_option_ltp(self.pe.locked_instrument or "")),
            "health": ks.get_status(),
        }
