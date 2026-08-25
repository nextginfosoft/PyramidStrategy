"""
Destiny Strategy Engine (NIFTY Level-Based Option Buying)
========================================================
PE Strategy (Resistance R):
- When NIFTY spot hits or reaches >= R:
  - Buy 1 lot ATM+50 PE (same-day expiry, except Tuesdays -> next weekly expiry).
  - Target = 30 pts, Stop Loss = 30 pts.
  - No further entry on R once completed for PE.

CE Strategy (Support S):
- When NIFTY spot hits or reaches <= S:
  - Buy 1 lot ATM-50 CE (same-day expiry, except Tuesdays -> next weekly expiry).
  - Target = 30 pts, Stop Loss = 30 pts.
  - No further entry on S once completed for CE.

General Rules:
1. Tuesday rule handled by option_selector (next weekly expiry).
2. After target achieved at R or S, no re-entry from that level on same day.
3. Square off all open positions by 3:20 PM.
4. No fresh entries after 2:30 PM for same-day expiry trades.
"""

import asyncio
from decimal import Decimal
from datetime import datetime, date, time
from typing import Optional, Dict, Any, Callable
from loguru import logger

from app.db.database import SessionLocal
from app.models.models import StrategyConfig, Trade, DailyPnL, User
from app.core.option_selector import get_option_details, estimate_option_price
from app.core.order_manager import OrderManager
from app.core.time_rules import is_tuesday, is_entry_allowed, is_squareoff_time


class DestinyStrategyEngine:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.is_running = False

        # Config parameters
        self.r_level: Optional[Decimal] = None
        self.s_level: Optional[Decimal] = None
        self.lot_size: int = 75
        self.target_pts: Decimal = Decimal("30.00")
        self.sl_pts: Decimal = Decimal("30.00")
        self.paper_trade: bool = True
        self.squareoff_time_str: str = "15:20"

        self.last_nifty_price: Optional[Decimal] = None
        self.nifty_prev_close: Optional[Decimal] = Decimal("24175.70")
        self._option_ltp: Dict[str, Decimal] = {}

        # Trade State tracking for the day
        self.active_pe_trade: Optional[Dict[str, Any]] = None
        self.active_ce_trade: Optional[Dict[str, Any]] = None

        self.r_level_completed: bool = False
        self.s_level_completed: bool = False

        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None

        # Post-exit target tracking trades (symbol -> list of trade IDs)
        self.post_exit_trades: Dict[str, list] = {}
        self._processing_option_symbols: set = set()

        self.order_manager = OrderManager(user_id=self.user_id)
        self.broadcast_fn: Optional[Callable] = None

    def start(self):
        """Start the engine and load configuration."""
        self._load_config()
        self.is_running = True
        from datetime import datetime
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        self.started_at = datetime.now(ist).strftime("%I:%M:%S %p")
        self.stopped_at = None
        logger.info(f"[DestinyEngine] User {self.user_id}: Started at {self.started_at}. R={self.r_level}, S={self.s_level}")
        
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_engine_started(paper_trade=self.paper_trade, strategy_type="DESTINY")
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to send engine started alert: {e}")

        # Gamification: motivational quote on engine start
        try:
            import asyncio
            from app.gamification.hooks import fire_engine_start_quote
            asyncio.create_task(fire_engine_start_quote(self.user_id, paper_trade=self.paper_trade))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Gamification engine start hook failed (non-critical): {e}")

        self.r_level_completed = False
        self.s_level_completed = False
        self.load_existing_trades()

    def load_existing_trades(self):
        """Restore active trade state, completed levels, and post-exit tracking after mid-day server restarts."""
        self.post_exit_trades = {}
        try:
            with SessionLocal() as db:
                from app.models.models import Trade
                from app.core.time_rules import today_ist
                target_date = today_ist()

                all_trades = db.query(Trade).filter(
                    Trade.user_id == self.user_id,
                    Trade.trade_date == target_date
                ).all()

                for t in all_trades:
                    symbol = t.instrument
                    # Restore active open trades
                    if t.status == "OPEN" and t.action == "BUY":
                        trade_info = {
                            "db_id": t.id,
                            "symbol": symbol,
                            "side": t.side,
                            "level": t.level,
                            "entry_price": Decimal(str(t.avg_price)) if t.avg_price else Decimal("100.00"),
                            "target_price": Decimal(str(t.avg_price or 100)) + self.target_pts,
                            "sl_price": Decimal(str(t.avg_price or 100)) - self.sl_pts,
                            "qty": t.qty or self.lot_size,
                            "expiry": str(t.expiry) if t.expiry else "",
                            "entry_time": t.created_at.isoformat() if t.created_at else datetime.now().isoformat(),
                        }
                        if t.side == "PE":
                            self.active_pe_trade = trade_info
                        else:
                            self.active_ce_trade = trade_info
                        self._subscribe_option(symbol)
                    
                    # Restore completed levels for day if exited
                    elif t.status in ("TARGET", "SL", "SQUAREOFF", "CLOSED"):
                        if t.side == "PE":
                            self.r_level_completed = True
                        elif t.side == "CE":
                            self.s_level_completed = True

                    # Restore post-exit tracking for TARGET trades
                    if t.status == "TARGET":
                        if symbol not in self.post_exit_trades:
                            self.post_exit_trades[symbol] = []
                        if t.id not in self.post_exit_trades[symbol]:
                            self.post_exit_trades[symbol].append(t.id)
                        self._subscribe_option(symbol)

            logger.info(
                f"[DestinyEngine] User {self.user_id}: Restored existing trades | "
                f"PE_Active={bool(self.active_pe_trade)}, PE_Completed={self.r_level_completed} | "
                f"CE_Active={bool(self.active_ce_trade)}, CE_Completed={self.s_level_completed}"
            )
        except Exception as e:
            logger.warning(f"[DestinyEngine] Error loading existing trades: {e}")

    def stop(self):
        """Stop the engine."""
        self.is_running = False
        from datetime import datetime
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        self.stopped_at = datetime.now(ist).strftime("%I:%M:%S %p")
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_engine_stopped(strategy_type="DESTINY")
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to send engine stopped alert: {e}")

        # Gamification: motivational quote on engine stop
        try:
            import asyncio
            from app.gamification.hooks import fire_engine_stop_quote
            asyncio.create_task(fire_engine_stop_quote(self.user_id))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Gamification engine stop hook failed (non-critical): {e}")

    @property
    def mock_feed(self):
        """Mock feed placeholder compatibility object for destiny engine."""
        class _DummyMockFeed:
            def stop(self):
                pass
        return _DummyMockFeed()

    def daily_reset(self):
        """Reset trade state tracking for the day."""
        self.active_pe_trade = None
        self.active_ce_trade = None
        self.r_level_completed = False
        self.s_level_completed = False
        logger.info(f"[DestinyEngine] User {self.user_id}: Daily trade state reset complete.")

    def load_config(self, config_dict: Optional[Dict[str, Any]] = None):
        """Dynamic runtime configuration reload."""
        if config_dict:
            if "r1" in config_dict and config_dict["r1"]:
                self.r_level = Decimal(str(config_dict["r1"]))
            if "s1" in config_dict and config_dict["s1"]:
                self.s_level = Decimal(str(config_dict["s1"]))
            if "lot_size" in config_dict:
                self.lot_size = int(config_dict["lot_size"])
            if "target_points" in config_dict:
                self.target_pts = Decimal(str(config_dict["target_points"]))
            if "sl_points" in config_dict:
                self.sl_pts = Decimal(str(config_dict["sl_points"]))
            if "paper_trade" in config_dict:
                self.paper_trade = bool(config_dict["paper_trade"])
                self.order_manager.paper_trade = self.paper_trade
            if "squareoff_time" in config_dict:
                self.squareoff_time_str = str(config_dict["squareoff_time"])
        else:
            self._load_config()

    def _load_config(self):
        db = SessionLocal()
        try:
            config = db.query(StrategyConfig).filter(
                StrategyConfig.user_id == self.user_id,
                StrategyConfig.is_active == True,
                StrategyConfig.strategy_type == "DESTINY"
            ).order_by(StrategyConfig.id.desc()).first()
            if not config:
                config = db.query(StrategyConfig).filter(
                    StrategyConfig.user_id == self.user_id,
                    StrategyConfig.is_active == True
                ).order_by(StrategyConfig.id.desc()).first()
            if config:
                self.r_level = Decimal(str(config.r1)) if config.r1 else None
                self.s_level = Decimal(str(config.s1)) if config.s1 else None
                self.lot_size = config.lot_size or 75
                self.target_pts = Decimal(str(config.target_points)) if config.target_points else Decimal("30.00")
                self.sl_pts = Decimal(str(config.sl_points)) if config.sl_points else Decimal("30.00")
                self.paper_trade = config.paper_trade
                self.order_manager.paper_trade = self.paper_trade
                self.squareoff_time_str = config.squareoff_time or "15:20"
            else:
                logger.warning(f"[DestinyEngine] User {self.user_id}: No StrategyConfig found in DB.")
        finally:
            db.close()

    async def _broadcast(self, event_type: str, data: Dict[str, Any]):
        if self.broadcast_fn:
            try:
                await self.broadcast_fn(self.user_id, {"type": event_type, "data": data, "strategy": "DESTINY"})
            except Exception as e:
                logger.error(f"[DestinyEngine] Broadcast error: {e}")

    async def on_option_tick(self, symbol: str, ltp: Decimal):
        """Callback from KiteTicker for option price updates."""
        self._option_ltp[symbol] = ltp

        # Track active high/low during position lifetime and sync to DB
        for trade in [self.active_pe_trade, self.active_ce_trade]:
            if trade and trade.get("symbol") == symbol:
                import pytz
                from datetime import datetime
                now = datetime.now(pytz.utc)
                updated = False
                if trade.get("active_high") is None or ltp > trade["active_high"]:
                    trade["active_high"] = ltp
                    trade["active_high_time"] = now
                    updated = True
                if trade.get("active_low") is None or ltp < trade["active_low"]:
                    trade["active_low"] = ltp
                    trade["active_low_time"] = now
                    updated = True

                if updated and trade.get("db_trade_id"):
                    try:
                        with SessionLocal() as db:
                            from app.models.models import Trade
                            db_trade = db.query(Trade).filter(Trade.id == trade["db_trade_id"]).first()
                            if db_trade:
                                db_trade.active_high = trade["active_high"]
                                db_trade.active_high_time = trade["active_high_time"]
                                db_trade.active_low = trade["active_low"]
                                db_trade.active_low_time = trade["active_low_time"]
                                db.commit()
                    except Exception as e:
                        logger.warning(f"[DestinyEngine] Error syncing active high/low to DB: {e}")

        await self._process_post_exit_tick(symbol, ltp)

    async def _process_post_exit_tick(self, symbol: str, ltp: Decimal):
        """Check and update post-exit high/low for completed target trades on this instrument."""
        if not hasattr(self, "post_exit_trades") or not self.post_exit_trades:
            return

        trade_ids = self.post_exit_trades.get(symbol)
        if not trade_ids:
            return

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
        except Exception as e:
            logger.warning(f"[DestinyEngine] Error in _process_post_exit_tick: {e}")
        finally:
            self._processing_option_symbols.discard(symbol)

    async def _record_320_prices(self, nifty_ltp: Optional[Decimal] = None):
        """Fetch and update price_at_320 for all trades executed today and clean post-exit tracking memory."""
        try:
            from app.core.time_rules import today_ist
            target_date = today_ist()
            with SessionLocal() as db:
                from app.models.models import Trade
                trades = db.query(Trade).filter(
                    Trade.user_id == self.user_id,
                    Trade.trade_date == target_date,
                    Trade.price_at_320.is_(None)
                ).all()

                if trades:
                    updated = False
                    for t in trades:
                        price = self.get_option_ltp(t.instrument, nifty_ltp)
                        if price is not None:
                            t.price_at_320 = Decimal(str(price))
                            updated = True

                    if updated:
                        db.commit()
                        logger.info(f"[DestinyEngine] User {self.user_id}: Recorded 3:20 PM prices for today's trades")

            # Clean post-exit tracking memory after market close
            if hasattr(self, "post_exit_trades"):
                self.post_exit_trades.clear()
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to record 3:20 PM prices: {e}")

    def _get_side_status(self, side: str, nifty_ltp: Optional[Decimal] = None) -> Dict[str, Any]:
        trade = self.active_ce_trade if side == "CE" else self.active_pe_trade
        completed = self.s_level_completed if side == "CE" else self.r_level_completed

        state = "L1_ENTERED" if trade else ("BLOCKED" if completed else "IDLE")
        lots = 1 if trade else 0
        locked_strike = trade.get("strike") if trade else None
        locked_instrument = trade.get("symbol") if trade else None
        entry_avg_price = float(trade.get("entry_price")) if trade and trade.get("entry_price") is not None else None
        active_high = float(trade.get("active_high")) if trade and trade.get("active_high") is not None else None
        active_low = float(trade.get("active_low")) if trade and trade.get("active_low") is not None else None

        current_ltp = None
        unrealized_pnl = None

        if trade:
            symbol = trade.get("symbol")
            if symbol and symbol in self._option_ltp:
                current_ltp = float(self._option_ltp[symbol])
            elif nifty_ltp is not None and symbol:
                current_ltp = float(estimate_option_price(symbol, nifty_ltp))

            if current_ltp is not None and entry_avg_price is not None:
                unrealized_pnl = round((current_ltp - entry_avg_price) * self.lot_size, 2)

        return {
            "state": state,
            "lots": lots,
            "locked_strike": locked_strike,
            "locked_instrument": locked_instrument,
            "entry_avg_price": entry_avg_price,
            "current_ltp": current_ltp,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": 0.0,
            "active_high": active_high,
            "active_low": active_low,
            "blocked_levels": ["L1"] if completed and not trade else [],
            "trade": trade,
        }

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
                logger.warning(f"[DestinyEngine] Error fetching live NIFTY previous close: {e}")

        ce_status = self._get_side_status("CE", nifty_ltp)
        pe_status = self._get_side_status("PE", nifty_ltp)

        status = {
            "type": "strategy_status",
            "user_id": self.user_id,
            "data": {
                "nifty_ltp": float(nifty_ltp),
                "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
                "is_running": self.is_running,
                "paper_trade": self.paper_trade,
                "entries_allowed": is_entry_allowed(squareoff_time_str=self.squareoff_time_str),
                "squareoff_triggered": is_squareoff_time(squareoff_time_str=self.squareoff_time_str),
                "ce": ce_status,
                "pe": pe_status,
                "health": ks.get_status(),
                "strategy_type": "DESTINY",
            },
        }
        await self.broadcast_fn(self.user_id, status)

    async def on_nifty_tick(self, nifty_ltp: Decimal):
        """Process incoming NIFTY spot tick."""
        prev_nifty = self.last_nifty_price
        self.last_nifty_price = nifty_ltp
        await self._broadcast_status(nifty_ltp)

        if not self.is_running:
            return

        from app.config import settings
        from app.core.time_rules import now_ist
        now = now_ist()
        current_time = now.time()
        # Check and record price at 3:20 PM IST (15:20) for all today's traded instruments
        if current_time.hour == 15 and current_time.minute >= 20 and not getattr(self, "_recorded_320_price", False):
            self._recorded_320_price = True
            import asyncio
            asyncio.create_task(self._record_320_prices(nifty_ltp))

        # Rule 3: 3:20 PM Square Off
        sq_h, sq_m = map(int, self.squareoff_time_str.split(":"))
        if current_time >= time(sq_h, sq_m) and getattr(settings, "APP_ENV", "") != "testing":
            await self._squareoff_all("3:20 PM Cutoff Time Reached", nifty_ltp)
            return

        # Check Active Trades SL & Target
        await self._check_active_trade_exits(nifty_ltp)

        # Rule 4: No fresh entries after 2:30 PM for same-day expiry
        is_tues = is_tuesday(now.date())
        if current_time > time(14, 30) and not is_tues and getattr(settings, "APP_ENV", "") != "testing":
            return

        # Entry Case 1: PE Strategy (Resistance R crossover: prev_nifty < R and nifty_ltp >= R)
        if self.r_level and not self.r_level_completed and not self.active_pe_trade:
            if prev_nifty is not None and prev_nifty < self.r_level and nifty_ltp >= self.r_level:
                await self._enter_trade(side="PE", nifty_ltp=nifty_ltp, trigger_level=self.r_level)
            elif prev_nifty is None and nifty_ltp >= self.r_level:
                await self._enter_trade(side="PE", nifty_ltp=nifty_ltp, trigger_level=self.r_level)

        # Entry Case 2: CE Strategy (Support S crossover: prev_nifty > S and nifty_ltp <= S)
        if self.s_level and not self.s_level_completed and not self.active_ce_trade:
            if prev_nifty is not None and prev_nifty > self.s_level and nifty_ltp <= self.s_level:
                await self._enter_trade(side="CE", nifty_ltp=nifty_ltp, trigger_level=self.s_level)
            elif prev_nifty is None and nifty_ltp <= self.s_level:
                await self._enter_trade(side="CE", nifty_ltp=nifty_ltp, trigger_level=self.s_level)

    def get_full_status(self) -> Dict[str, Any]:
        """Return full current engine status for REST API and UI rendering."""
        from app.db.database import get_redis_client
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

        ce_status = self._get_side_status("CE", nifty_ltp)
        pe_status = self._get_side_status("PE", nifty_ltp)

        return {
            "is_running": self.is_running,
            "paper_trade": self.paper_trade,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "nifty_ltp": float(nifty_ltp) if nifty_ltp else None,
            "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
            "entries_allowed": is_entry_allowed(squareoff_time_str=self.squareoff_time_str),
            "squareoff_triggered": is_squareoff_time(squareoff_time_str=self.squareoff_time_str),
            "ce": ce_status,
            "pe": pe_status,
            "health": ks.get_status(),
            "strategy_type": "DESTINY",
        }

    # ── Kite Option Subscription ─────────────────────────────────────────────

    def _subscribe_option(self, symbol: Optional[str]):
        """Subscribe to live option ticks after entry."""
        if not symbol:
            return
        try:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if kite_service.is_authenticated() and kite_service._ticker_running:
                kite_service.subscribe_option(symbol)
        except Exception as e:
            logger.warning(f"[DestinyEngine] Option subscribe failed (non-critical): {e}")

    def _unsubscribe_option(self, symbol: Optional[str]):
        """Unsubscribe from option ticks after exit."""
        if not symbol:
            return
        try:
            from app.services.kite_service import get_user_kite_service
            kite_service = get_user_kite_service(self.user_id)
            if kite_service.is_authenticated():
                kite_service.unsubscribe_option(symbol)
        except Exception as e:
            logger.warning(f"[DestinyEngine] Option unsubscribe failed (non-critical): {e}")

    def get_option_ltp(self, symbol: str, nifty_ltp: Optional[Decimal] = None) -> Decimal:
        """Return cached option LTP from live ticks, or query Kite, or fallback to estimate_option_price."""
        if not symbol:
            return Decimal("100.00")
        try:
            from app.services.kite_service import get_user_kite_service
            ks = get_user_kite_service(self.user_id)
            if ks.is_authenticated():
                live_ltp = ks.get_option_ltp(symbol)
                if live_ltp is not None:
                    self._option_ltp[symbol] = live_ltp
                    return live_ltp
        except Exception as e:
            logger.warning(f"[DestinyEngine] Error fetching live option LTP for {symbol}: {e}")

        if nifty_ltp is not None:
            price = estimate_option_price(symbol, nifty_ltp)
            self._option_ltp[symbol] = price
            return price
        elif symbol in self._option_ltp:
            return self._option_ltp[symbol]
        elif self.last_nifty_price is not None:
            return estimate_option_price(symbol, self.last_nifty_price)
        return Decimal("100.00")

    async def _enter_trade(self, side: str, nifty_ltp: Decimal, trigger_level: Decimal):
        opt_details = get_option_details(side, nifty_ltp)
        symbol = opt_details["symbol"]
        exp_date = opt_details["expiry"]
        mock_ltp = self.get_option_ltp(symbol, nifty_ltp)

        total_qty = self.lot_size
        level_str = "R" if side == "PE" else "S"

        db = SessionLocal()
        try:
            order_res = self.order_manager.place_buy_order(
                db=db,
                side=side,
                level=level_str,
                instrument=symbol,
                strike=opt_details["strike"],
                expiry=opt_details["expiry"],
                lots=1,
                lot_size=self.lot_size,
                trigger_nifty=nifty_ltp,
                mock_ltp=mock_ltp if self.paper_trade else None,
            )
            db_id = order_res["trade_id"]
            fill_price = Decimal(str(order_res["fill_price"]))
            db.commit()
        except Exception as e:
            logger.error(f"[DestinyEngine] Order placement failed for {side}: {e}", exc_info=True)
            return
        finally:
            db.close()

        target_price = fill_price + self.target_pts
        sl_price = fill_price - self.sl_pts

        trade_info = {
            "db_id": db_id,
            "symbol": symbol,
            "strike": opt_details["strike"],
            "side": side,
            "level": level_str,
            "entry_price": fill_price,
            "target_price": target_price,
            "sl_price": sl_price,
            "qty": total_qty,
            "expiry": str(exp_date),
            "entry_time": datetime.now().isoformat(),
        }

        if side == "PE":
            self.active_pe_trade = trade_info
        else:
            self.active_ce_trade = trade_info

        # Cache & Subscribe live ticks for option symbol
        self._option_ltp[symbol] = fill_price
        self._subscribe_option(symbol)

        logger.info(
            f"[DestinyEngine] ENTRY {side} (Paper={self.paper_trade}): {symbol} @ {fill_price:.2f} | "
            f"Target={target_price:.2f}, SL={sl_price:.2f} | NIFTY={nifty_ltp}"
        )

        await self._broadcast("TRADE_ENTRY", trade_info)

        # Telegram / WhatsApp Notifications
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            ns.notify_trade_entry(
                side=side,
                level=level_str,
                instrument=symbol,
                lots=1,
                fill_price=fill_price,
                nifty_ltp=nifty_ltp,
                strategy_type="DESTINY",
            )
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to send entry notification: {e}")

        # Gamification: motivational quote on trade entry
        try:
            from app.gamification.hooks import fire_entry_quote
            sl_price = float(sl_price) if sl_price is not None else None
            asyncio.create_task(fire_entry_quote(
                self.user_id, side, level_str,
                instrument=symbol,
                fill_price=float(fill_price),
                sl_price=sl_price,
            ))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Gamification entry hook failed (non-critical): {e}")

        # AI Trade Analysis Task
        import asyncio
        asyncio.create_task(self._notify_ai("ENTRY", side, level_str, nifty_ltp))

    async def _check_active_trade_exits(self, nifty_ltp: Decimal):
        for side, active_trade in [("PE", self.active_pe_trade), ("CE", self.active_ce_trade)]:
            if not active_trade:
                continue

            symbol = active_trade["symbol"]
            current_opt_price = self.get_option_ltp(symbol, nifty_ltp)

            # Target Check
            if current_opt_price >= active_trade["target_price"]:
                await self._exit_trade(side, "TARGET", current_opt_price, nifty_ltp)
            # Stop Loss Check
            elif current_opt_price <= active_trade["sl_price"]:
                await self._exit_trade(side, "SL", current_opt_price, nifty_ltp)

    async def _exit_trade(self, side: str, reason: str, exit_price: Decimal, nifty_ltp: Decimal):
        trade = self.active_pe_trade if side == "PE" else self.active_ce_trade
        if not trade:
            return

        symbol = trade["symbol"]
        level_str = trade["level"]

        db = SessionLocal()
        try:
            self.order_manager.place_exit_order(
                db=db,
                side=side,
                instrument=symbol,
                strike=trade.get("strike", 24150),
                qty=trade["qty"],
                reason=reason,
                entry_avg_price=trade["entry_price"],
                mock_ltp=exit_price if self.paper_trade else None,
                trigger_nifty=nifty_ltp,
                lot_size=self.lot_size,
            )
            db.commit()
        except Exception as e:
            logger.error(f"[DestinyEngine] Exit order failed for {side} {symbol}: {e}")
        finally:
            db.close()

        # Unsubscribe live ticks for option symbol after exit
        self._unsubscribe_option(symbol)

        pnl_pts = exit_price - trade["entry_price"]
        total_pnl = pnl_pts * Decimal(str(trade["qty"]))

        logger.info(
            f"[DestinyEngine] EXIT {side} ({reason}, Paper={self.paper_trade}): {symbol} @ {exit_price:.2f} | "
            f"PnL = Rs. {total_pnl:.2f}"
        )

        # Rule 6: If target or SL hit, level completed for day
        if side == "PE":
            self.r_level_completed = True
            self.active_pe_trade = None
        else:
            self.s_level_completed = True
            self.active_ce_trade = None

        await self._broadcast("TRADE_EXIT", {
            "side": side,
            "reason": reason,
            "exit_price": float(exit_price),
            "pnl": float(total_pnl),
            "symbol": symbol,
        })

        # Telegram / WhatsApp Notifications
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            if reason == "TARGET":
                ns.notify_target_hit(
                    side=side,
                    instrument=symbol,
                    lots=trade.get("lots", 1),
                    exit_price=exit_price,
                    entry_avg=trade["entry_price"],
                    pnl_rupees=total_pnl,
                    strategy_type="DESTINY",
                )
            elif reason == "SL":
                ns.notify_sl_hit(
                    side=side,
                    instrument=symbol,
                    lots=trade.get("lots", 1),
                    exit_price=exit_price,
                    entry_avg=trade["entry_price"],
                    pnl_rupees=total_pnl,
                    strategy_type="DESTINY",
                )
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to send exit notification: {e}")

        # Gamification: motivational quote on exit
        try:
            from app.gamification.hooks import fire_target_quote, fire_sl_quote
            if reason == "TARGET":
                asyncio.create_task(fire_target_quote(
                    self.user_id, side,
                    instrument=symbol,
                    pnl_rupees=total_pnl,
                ))
            elif reason == "SL":
                asyncio.create_task(fire_sl_quote(
                    self.user_id, side,
                    instrument=symbol,
                    pnl_rupees=total_pnl,
                ))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Gamification exit hook failed (non-critical): {e}")

        # AI Trade Analysis Task
        import asyncio
        asyncio.create_task(self._notify_ai("EXIT", side, level_str, nifty_ltp))

    async def _notify_ai(self, event_type: str, side: str, level: str, nifty_ltp: Decimal):
        """Asynchronously trigger AI trade analysis after entry or exit."""
        try:
            from app.api.routes.ai import generate_trade_analysis_task
            await generate_trade_analysis_task(
                user_id=self.user_id,
                event_type=event_type,
                side=side,
                level=level,
                nifty_ltp=float(nifty_ltp),
                strategy_type="DESTINY",
            )
        except Exception as e:
            logger.debug(f"[DestinyEngine] AI notification task (non-critical): {e}")

    async def _squareoff_all(self, reason: str, nifty_ltp: Decimal):
        for side in ["PE", "CE"]:
            trade = self.active_pe_trade if side == "PE" else self.active_ce_trade
            if trade:
                symbol = trade["symbol"]
                current_price = self.get_option_ltp(symbol, nifty_ltp)
                await self._exit_trade(side, f"SQUAREOFF ({reason})", current_price, nifty_ltp)

        # Query total CE & PE PnL for squareoff summary notification
        ce_pnl = Decimal("0")
        pe_pnl = Decimal("0")
        try:
            with SessionLocal() as db:
                from app.core.time_rules import today_ist
                target_date = today_ist()
                all_trades = db.query(Trade).filter(
                    Trade.user_id == self.user_id,
                    Trade.trade_date == target_date,
                    Trade.status.in_(["TARGET", "SL", "SQUAREOFF", "CLOSED"]),
                    Trade.action == "BUY"
                ).all()
                for t in all_trades:
                    pnl_val = Decimal(str(t.pnl or 0))
                    if t.side == "CE":
                        ce_pnl += pnl_val
                    elif t.side == "PE":
                        pe_pnl += pnl_val
        except Exception as db_err:
            logger.error(f"[DestinyEngine] Failed to query today's trades for squareoff P&L: {db_err}")

        # Send Telegram / WhatsApp squareoff alert
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(self.user_id)
            ns.load_from_db()
            sq_time = self.squareoff_time_str or "15:20"
            ns.notify_squareoff(ce_pnl, pe_pnl, sq_time, strategy_type="DESTINY")
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to send squareoff alert: {e}")

        # Gamification: motivational quote on squareoff
        try:
            from app.gamification.hooks import fire_squareoff_quote
            total_pnl = ce_pnl + pe_pnl
            asyncio.create_task(fire_squareoff_quote(self.user_id, total_pnl=total_pnl))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Gamification squareoff hook failed (non-critical): {e}")

        # Send EOD report immediately upon squareoff completion
        try:
            from app.services.reporting import send_daily_report
            from app.core.time_rules import today_ist
            asyncio.create_task(send_daily_report(self.user_id, today_ist()))
        except Exception as e:
            logger.warning(f"[DestinyEngine] Failed to trigger EOD PDF report on squareoff: {e}")

        self.stop()

    async def emergency_exit(self) -> Dict[str, Any]:
        """Emergency exit all positions."""
        count = 0
        pnl = Decimal("0.00")
        for side in ["PE", "CE"]:
            trade = self.active_pe_trade if side == "PE" else self.active_ce_trade
            if trade:
                symbol = trade["symbol"]
                est_price = self.get_option_ltp(symbol)
                await self._exit_trade(side, "EMERGENCY_EXIT", est_price, self.last_nifty_price or Decimal("24000"))
                count += 1
        return {"status": "success", "exited_count": count, "pnl_rupees": float(pnl)}
