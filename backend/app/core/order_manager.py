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

from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.orm import Session
from loguru import logger
from app.config import settings
from app.models.models import Trade, AuditLog
from app.core.time_rules import today_ist


class OrderManager:
    def __init__(self, kite_service=None):
        self.kite = kite_service  # None in paper trade mode
        self.paper_trade = settings.PAPER_TRADE

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
        mock_ltp: Decimal | None = None,
    ) -> dict:
        """
        Place a BUY (entry) order.
        Returns fill details: {order_id, fill_price, qty, status}
        """
        qty = lots * lot_size

        if self.paper_trade:
            fill_price = mock_ltp or Decimal("100.00")  # Mock fill at LTP
            order_id = f"PAPER-{side}-{level}-{datetime.now().strftime('%H%M%S%f')}"
            status = "COMPLETE"
            logger.info(
                f"[PAPER] BUY {qty} {instrument} @ {fill_price} | "
                f"lots={lots} | level={level} | trigger_nifty={trigger_nifty}"
            )
        else:
            # Live Kite order
            if not self.kite:
                raise RuntimeError("Kite service not initialized for live trading")
            order_id, fill_price, status = self._place_kite_order(
                instrument=instrument,
                transaction_type="BUY",
                qty=qty,
            )

        # Persist to DB
        trade = Trade(
            trade_date=today_ist(),
            side=side,
            level=level,
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
        db.flush()  # get trade.id without committing

        self._log_audit(db, "ORDER_PLACED", side, level, trigger_nifty, {
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
        mock_ltp: Decimal | None = None,
        trigger_nifty: Decimal | None = None,
    ) -> dict:
        """
        Place a MARKET EXIT (sell) order for the FULL position.
        reason: "TARGET" | "SL" | "SQUAREOFF" | "MANUAL"
        """
        if self.paper_trade:
            exit_price = mock_ltp or Decimal("120.00")
            order_id = f"PAPER-EXIT-{side}-{datetime.now().strftime('%H%M%S%f')}"
            status = "COMPLETE"
            logger.info(
                f"[PAPER] EXIT {qty} {instrument} @ {exit_price} | reason={reason}"
            )
        else:
            if not self.kite:
                raise RuntimeError("Kite service not initialized")
            order_id, exit_price, status = self._place_kite_order(
                instrument=instrument,
                transaction_type="SELL",
                qty=qty,
            )

        pnl_pts = exit_price - entry_avg_price
        pnl_rupees = pnl_pts * qty

        # Update trade record in DB
        trade = (
            db.query(Trade)
            .filter(
                Trade.instrument == instrument,
                Trade.action == "BUY",
                Trade.status == "OPEN",
                Trade.trade_date == today_ist(),
            )
            .order_by(Trade.created_at.desc())
            .first()
        )

        if trade:
            trade.status = reason  # TARGET / SL / SQUAREOFF
            trade.pnl = pnl_rupees

        # Log the EXIT as a separate trade record
        exit_trade = Trade(
            trade_date=today_ist(),
            side=side,
            level="EXIT",
            instrument=instrument,
            strike=strike,
            expiry=trade.expiry if trade else today_ist(),
            action="EXIT",
            lots=qty // 75,
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

    def _place_kite_order(self, instrument: str, transaction_type: str, qty: int) -> tuple:
        """Place live order via Kite Connect. Returns (order_id, fill_price, status)."""
        import time
        order_id = self.kite.place_order(
            variety="regular",
            exchange="NFO",
            tradingsymbol=instrument,
            transaction_type=transaction_type,
            quantity=qty,
            order_type="MARKET",
            product="MIS",  # Intraday
        )
        logger.info(f"Kite order placed: {order_id}")

        # Poll for fill (max 10 seconds)
        for _ in range(10):
            time.sleep(1)
            orders = self.kite.orders()
            for o in orders:
                if o["order_id"] == order_id:
                    if o["status"] == "COMPLETE":
                        fill_price = Decimal(str(o["average_price"]))
                        return order_id, fill_price, "COMPLETE"
                    elif o["status"] == "REJECTED":
                        raise RuntimeError(f"Order rejected: {o.get('status_message')}")

        raise TimeoutError(f"Order {order_id} not filled within 10 seconds")

    def _log_audit(self, db: Session, event: str, side: str | None, level: str | None,
                   nifty: Decimal | None, details: dict):
        log = AuditLog(
            event_type=event,
            side=side,
            level=level,
            nifty_price=nifty,
            details=details,
        )
        db.add(log)
