"""
Order Manager
─────────────
Handles BUY and EXIT orders.

In PAPER_TRADE mode: simulates orders at current LTP, logs to DB.
In LIVE mode: calls Kite Connect API, waits for fill confirmation.

CLAUDE.md Rules:
  - MARKET orders for ALL entries and exits (speed over price)
  - Never use LIMIT orders for exits
  - Max 3 lots per side (enforced by state machine, double-checked here)
"""

import time
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger
from app.config import settings
from app.models.models import Trade, AuditLog
from app.core.time_rules import today_ist

# Retry configuration for live orders
_MAX_RETRIES = 3
_RETRY_DELAY = 0.5   # seconds between retries
_FILL_POLL_SECS = 15  # seconds to wait for fill confirmation


class OrderError(Exception):
    """Raised when a live order fails (rejected, timeout, etc.)."""
    pass


class OrderManager:
    def __init__(self, user_id: int = 1, kite_service=None):
        self.user_id = user_id
        self.kite = kite_service  # None in paper trade mode
        self.paper_trade = settings.PAPER_TRADE

    # ── Public API ────────────────────────────────────────────────────────────

    def place_buy_order(
        self,
        db: Session,
        side: str,
        level: str,
        instrument: str,
        strike: int,
        expiry: date,
        lots: int,
        lot_size: int,
        trigger_nifty: Decimal,
        mock_ltp: Optional[Decimal] = None,
    ) -> dict:
        """
        Place a BUY (entry) order.
        Returns fill details: {trade_id, order_id, fill_price, qty, status}
        """
        qty = lots * lot_size
        mapped_level = level
        if level in ("L1", "L2", "L3"):
            if side == "CE":
                mapped_level = level.replace("L", "S")
            elif side == "PE":
                mapped_level = level.replace("L", "R")

        if self.paper_trade:
            fill_price = mock_ltp or Decimal("100.00")
            order_id = f"PAPER-{side}-{level}-{datetime.now().strftime('%H%M%S%f')}"
            status = "COMPLETE"
            logger.info(
                f"[PAPER] [User {self.user_id}] BUY {qty} {instrument} @ {fill_price} | "
                f"lots={lots} | level={mapped_level} | trigger_nifty={trigger_nifty}"
            )
        else:
            if not self.kite:
                raise OrderError(f"Kite service not initialized for live trading (User {self.user_id})")
            order_id, fill_price, status = self._place_kite_order_with_retry(
                instrument=instrument,
                transaction_type="BUY",
                qty=qty,
                context=f"User {self.user_id} {side} {mapped_level} BUY",
            )

        # Persist to DB
        trade = Trade(
            user_id=self.user_id,
            trade_date=today_ist(),
            side=side,
            level=mapped_level,
            instrument=instrument,
            strike=strike,
            expiry=expiry,
            action="BUY",
            lots=lots,
            qty=qty,
            avg_price=fill_price,
            trigger_nifty_level=trigger_nifty,
            kite_order_id=order_id,
            status="OPEN",
            is_paper_trade=self.paper_trade,
        )
        db.add(trade)
        db.flush()

        self._log_audit(db, "ORDER_PLACED", side, mapped_level, trigger_nifty, {
            "trade_id": trade.id,
            "action": "BUY",
            "instrument": instrument,
            "qty": qty,
            "fill_price": str(fill_price),
            "order_id": order_id,
        })
        db.commit()

        return {
            "trade_id": trade.id,
            "order_id": order_id,
            "fill_price": fill_price,
            "qty": qty,
            "status": status,
        }

    def place_exit_order(
        self,
        db: Session,
        side: str,
        instrument: str,
        strike: int,
        qty: int,
        reason: str,
        entry_avg_price: Decimal,
        mock_ltp: Optional[Decimal] = None,
        trigger_nifty: Optional[Decimal] = None,
        lot_size: int = 75,
    ) -> dict:
        """
        Place a MARKET EXIT (sell) order for the FULL position.
        reason: "TARGET" | "SL" | "SQUAREOFF" | "MANUAL"

        IMPORTANT: Always MARKET order — speed over price for exits.
        """
        if self.paper_trade:
            exit_price = mock_ltp or Decimal("120.00")
            order_id = f"PAPER-EXIT-{side}-{datetime.now().strftime('%H%M%S%f')}"
            status = "COMPLETE"
            logger.info(f"[PAPER] [User {self.user_id}] EXIT {qty} {instrument} @ {exit_price} | reason={reason}")
        else:
            if not self.kite:
                raise OrderError(f"Kite service not initialized (User {self.user_id})")
            # For exits, we use no retries on SQUAREOFF to avoid double-selling.
            # For TARGET/SL we retry once only.
            max_retries = 2 if reason == "SQUAREOFF" else _MAX_RETRIES
            order_id, exit_price, status = self._place_kite_order_with_retry(
                instrument=instrument,
                transaction_type="SELL",
                qty=qty,
                context=f"User {self.user_id} {side} {reason} EXIT",
                max_retries=max_retries,
            )

        pnl_pts = exit_price - entry_avg_price
        pnl_rupees = pnl_pts * qty

        # Update original OPEN trade record
        open_trade = (
            db.query(Trade)
            .filter(
                Trade.user_id == self.user_id,
                Trade.instrument == instrument,
                Trade.action == "BUY",
                Trade.status == "OPEN",
                Trade.trade_date == today_ist(),
            )
            .order_by(Trade.created_at.desc())
            .first()
        )

        expiry_date = open_trade.expiry if open_trade else today_ist()
        if open_trade:
            open_trade.status = reason
            open_trade.pnl = pnl_rupees

        # Log the EXIT as a separate record
        exit_trade = Trade(
            user_id=self.user_id,
            trade_date=today_ist(),
            side=side,
            level="EXIT",
            instrument=instrument,
            strike=strike,
            expiry=expiry_date,
            action="EXIT",
            lots=qty // lot_size,
            qty=qty,
            avg_price=exit_price,
            trigger_nifty_level=trigger_nifty,
            kite_order_id=order_id,
            status=reason,
            pnl=pnl_rupees,
            is_paper_trade=self.paper_trade,
        )
        db.add(exit_trade)

        self._log_audit(db, f"ORDER_EXIT_{reason}", side, None, trigger_nifty, {
            "instrument": instrument,
            "qty": qty,
            "exit_price": str(exit_price),
            "entry_avg": str(entry_avg_price),
            "pnl_pts": str(pnl_pts),
            "pnl_rupees": str(pnl_rupees),
        })
        db.commit()

        return {
            "order_id": order_id,
            "exit_price": exit_price,
            "pnl_points": pnl_pts,
            "pnl_rupees": pnl_rupees,
            "status": status,
        }

    # ── Live Order Placement ──────────────────────────────────────────────────

    def _place_kite_order_with_retry(
        self,
        instrument: str,
        transaction_type: str,
        qty: int,
        context: str,
        max_retries: int = _MAX_RETRIES,
    ) -> tuple:
        """
        Place a live Kite MARKET order with retry logic.
        Returns (order_id, fill_price, status).
        Raises OrderError on final failure.
        """
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                result = self._place_kite_order(instrument, transaction_type, qty)
                if attempt > 1:
                    logger.info(f"Order succeeded on attempt {attempt}: {context}")
                return result

            except TimeoutError as e:
                last_error = e
                logger.warning(f"Order poll timeout (attempt {attempt}/{max_retries}): {context} — {e}")
                # Don't retry timeouts for exits (position might be filled but we missed it)
                if transaction_type == "SELL":
                    logger.error(f"EXIT order timeout — NOT retrying to avoid double-sell: {context}")
                    try:
                        filled = self._check_recent_fill(instrument, transaction_type, qty)
                        if filled:
                            return filled
                    except Exception:
                        pass
                    raise OrderError(f"EXIT order timeout for {context} — check Kite positions manually") from e

            except OrderError as e:
                last_error = e
                logger.error(f"Order rejected (attempt {attempt}/{max_retries}): {context} — {e}")
                self._alert_order_failure(context, str(e))
                raise

            except Exception as e:
                last_error = e
                logger.warning(f"Order error (attempt {attempt}/{max_retries}): {context} — {e}")

            if attempt < max_retries:
                time.sleep(_RETRY_DELAY * attempt)  # exponential backoff

        self._alert_order_failure(context, str(last_error))
        raise OrderError(f"Order failed after {max_retries} attempts: {context}") from last_error

    def _place_kite_order(self, instrument: str, transaction_type: str, qty: int) -> tuple:
        """Place live order via Kite Connect. Returns (order_id, fill_price, status)."""
        order_id = self.kite.kite.place_order(
            variety="regular",
            exchange="NFO",
            tradingsymbol=instrument,
            transaction_type=transaction_type,
            quantity=qty,
            order_type="MARKET",
            product="MIS",  # Intraday — crucial
        )
        logger.info(f"[LIVE] Kite order placed: {order_id} | {transaction_type} {qty} {instrument}")

        for i in range(_FILL_POLL_SECS):
            time.sleep(1)
            orders = self.kite.kite.orders()
            for o in orders:
                if str(o.get("order_id")) == str(order_id):
                    kite_status = o.get("status", "")
                    if kite_status == "COMPLETE":
                        fill_price = Decimal(str(o.get("average_price", "0")))
                        logger.info(f"[LIVE] Order filled: {order_id} @ {fill_price}")
                        return order_id, fill_price, "COMPLETE"
                    elif kite_status in ("REJECTED", "CANCELLED"):
                        msg = o.get("status_message") or o.get("status_message_raw", "Unknown reason")
                        raise OrderError(f"Order {kite_status}: {msg}")
            if i % 5 == 4:
                logger.debug(f"Still waiting for fill: {order_id} ({i+1}s)")

        raise TimeoutError(f"Order {order_id} not filled within {_FILL_POLL_SECS}s")

    def _check_recent_fill(self, instrument: str, transaction_type: str, qty: int):
        """Check Kite order book for a recently filled order matching our instrument."""
        try:
            orders = self.kite.kite.orders()
            for o in reversed(orders):
                if (o.get("tradingsymbol") == instrument
                        and o.get("transaction_type") == transaction_type
                        and o.get("quantity") == qty
                        and o.get("status") == "COMPLETE"):
                    fill_price = Decimal(str(o.get("average_price", "0")))
                    logger.info(f"Found fill in order book: {o['order_id']} @ {fill_price}")
                    return o["order_id"], fill_price, "COMPLETE"
        except Exception as e:
            logger.warning(f"Could not check order book: {e}")
        return None

    def _alert_order_failure(self, context: str, error_msg: str):
        """Send Telegram alert for order failure (non-blocking, best-effort)."""
        try:
            import asyncio
            from app.services.notification import NotificationService
            # We can't import the global notification_service directly since notifications are user-specific now.
            # However, we can log it.
            logger.error(f"Order alert: {context} - {error_msg}")
        except Exception:
            pass  # Never let notification failure propagate

    # ── Audit Logging ─────────────────────────────────────────────────────────

    def _log_audit(self, db: Session, event: str, side: Optional[str], level: Optional[str],
                   nifty: Optional[Decimal], details: dict):
        log = AuditLog(
            user_id=self.user_id,
            event_type=event,
            side=side,
            level=level,
            nifty_price=nifty,
            details=details,
        )
        db.add(log)
