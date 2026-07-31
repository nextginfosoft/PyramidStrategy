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

        self.order_manager = OrderManager()
        self.broadcast_fn: Optional[Callable] = None

    def start(self):
        """Start the engine and load configuration."""
        self._load_config()
        self.is_running = True
        logger.info(f"[DestinyEngine] User {self.user_id}: Started. R={self.r_level}, S={self.s_level}")

    def stop(self):
        """Stop the engine."""
        self.is_running = False
        logger.info(f"[DestinyEngine] User {self.user_id}: Stopped.")

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
            if "squareoff_time" in config_dict:
                self.squareoff_time_str = str(config_dict["squareoff_time"])
        else:
            self._load_config()

    def _load_config(self):
        db = SessionLocal()
        try:
            config = db.query(StrategyConfig).filter(StrategyConfig.user_id == self.user_id).order_by(StrategyConfig.id.desc()).first()
            if config:
                self.r_level = Decimal(str(config.r1)) if config.r1 else None
                self.s_level = Decimal(str(config.s1)) if config.s1 else None
                self.lot_size = config.lot_size or 75
                self.target_pts = Decimal(str(config.target_points)) if config.target_points else Decimal("30.00")
                self.sl_pts = Decimal(str(config.sl_points)) if config.sl_points else Decimal("30.00")
                self.paper_trade = config.paper_trade
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
                "ce": {"active": bool(self.active_ce_trade), "trade": self.active_ce_trade},
                "pe": {"active": bool(self.active_pe_trade), "trade": self.active_pe_trade},
                "health": ks.get_status(),
                "strategy_type": "DESTINY",
            },
        }
        await self.broadcast_fn(self.user_id, status)

    async def on_nifty_tick(self, nifty_ltp: Decimal):
        """Process incoming NIFTY spot tick."""
        self.last_nifty_price = nifty_ltp
        await self._broadcast_status(nifty_ltp)

        if not self.is_running:
            return

        now = datetime.now()
        current_time = now.time()

        # Rule 3: 3:20 PM Square Off
        sq_h, sq_m = map(int, self.squareoff_time_str.split(":"))
        if current_time >= time(sq_h, sq_m):
            await self._squareoff_all("3:20 PM Cutoff Time Reached", nifty_ltp)
            return

        # Check Active Trades SL & Target
        await self._check_active_trade_exits(nifty_ltp)

        # Rule 4: No fresh entries after 2:30 PM for same-day expiry
        is_tues = is_tuesday(now.date())
        if current_time > time(14, 30) and not is_tues:
            return

        # Entry Case 1: PE Strategy (Resistance R)
        if self.r_level and not self.r_level_completed and not self.active_pe_trade:
            if nifty_ltp >= self.r_level:
                await self._enter_trade(side="PE", nifty_ltp=nifty_ltp, trigger_level=self.r_level)

        # Entry Case 2: CE Strategy (Support S)
        if self.s_level and not self.s_level_completed and not self.active_ce_trade:
            if nifty_ltp <= self.s_level:
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

        return {
            "is_running": self.is_running,
            "paper_trade": self.paper_trade,
            "nifty_ltp": float(nifty_ltp) if nifty_ltp else None,
            "nifty_prev_close": float(self.nifty_prev_close) if self.nifty_prev_close else None,
            "entries_allowed": is_entry_allowed(squareoff_time_str=self.squareoff_time_str),
            "squareoff_triggered": is_squareoff_time(squareoff_time_str=self.squareoff_time_str),
            "ce": {"active": bool(self.active_ce_trade), "trade": self.active_ce_trade},
            "pe": {"active": bool(self.active_pe_trade), "trade": self.active_pe_trade},
            "health": ks.get_status(),
            "strategy_type": "DESTINY",
        }

    async def _enter_trade(self, side: str, nifty_ltp: Decimal, trigger_level: Decimal):
        exp_date, symbol = get_option_details(side, nifty_ltp)
        entry_price = estimate_option_price(symbol, nifty_ltp)

        target_price = entry_price + self.target_pts
        sl_price = entry_price - self.sl_pts
        total_qty = self.lot_size

        logger.info(
            f"[DestinyEngine] Placed {side} BUY order for {symbol} @ {entry_price:.2f} | "
            f"Qty={total_qty}, Trigger={trigger_level}, Target={target_price:.2f}, SL={sl_price:.2f}"
        )

        db = SessionLocal()
        try:
            trade_record = self.order_manager.place_buy_order(
                db=db,
                user_id=self.user_id,
                side=side,
                level="R" if side == "PE" else "S",
                lots=1,
                lot_size=self.lot_size,
                symbol=symbol,
                act_price=entry_price,
                avg_price=entry_price,
                target_price=target_price,
                sl_price=sl_price,
                paper_trade=self.paper_trade,
                trigger_nifty=nifty_ltp,
            )
            db_id = trade_record.id
            db.commit()
        except Exception as e:
            logger.error(f"[DestinyEngine] Order placement failed for {side}: {e}")
            return
        finally:
            db.close()

        trade_info = {
            "db_id": db_id,
            "symbol": symbol,
            "side": side,
            "level": "R" if side == "PE" else "S",
            "entry_price": entry_price,
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

        logger.info(
            f"[DestinyEngine] ENTRY {side} (Paper={self.paper_trade}): {symbol} @ {entry_price:.2f} | "
            f"Target={target_price:.2f}, SL={sl_price:.2f} | NIFTY={nifty_ltp}"
        )

        await self._broadcast("TRADE_ENTRY", trade_info)

    async def _check_active_trade_exits(self, nifty_ltp: Decimal):
        for side, active_trade in [("PE", self.active_pe_trade), ("CE", self.active_ce_trade)]:
            if not active_trade:
                continue

            symbol = active_trade["symbol"]
            current_opt_price = estimate_option_price(symbol, nifty_ltp)

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

        db = SessionLocal()
        try:
            self.order_manager.place_exit_order(
                db=db,
                trade_id=trade["db_id"],
                side=side,
                level=trade["level"],
                reason=reason,
                trigger_nifty=nifty_ltp,
                mock_ltp=exit_price if self.paper_trade else None,
            )
            db.commit()
        except Exception as e:
            logger.error(f"[DestinyEngine] Exit order failed for {side} {trade['symbol']}: {e}")
        finally:
            db.close()

        pnl_pts = exit_price - trade["entry_price"]
        total_pnl = pnl_pts * Decimal(str(trade["qty"]))

        logger.info(
            f"[DestinyEngine] EXIT {side} ({reason}, Paper={self.paper_trade}): {trade['symbol']} @ {exit_price:.2f} | "
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
            "symbol": trade["symbol"],
        })

    async def _squareoff_all(self, reason: str, nifty_ltp: Decimal):
        for side in ["PE", "CE"]:
            trade = self.active_pe_trade if side == "PE" else self.active_ce_trade
            if trade:
                current_price = estimate_option_price(trade["symbol"], nifty_ltp)
                await self._exit_trade(side, f"SQUAREOFF ({reason})", current_price, nifty_ltp)

    async def emergency_exit(self) -> Dict[str, Any]:
        """Emergency exit all positions."""
        count = 0
        pnl = Decimal("0.00")
        for side in ["PE", "CE"]:
            trade = self.active_pe_trade if side == "PE" else self.active_ce_trade
            if trade:
                est_price = trade["entry_price"]
                await self._exit_trade(side, "EMERGENCY_EXIT", est_price, Decimal("24000"))
                count += 1
        return {"status": "success", "exited_count": count, "pnl_rupees": float(pnl)}
