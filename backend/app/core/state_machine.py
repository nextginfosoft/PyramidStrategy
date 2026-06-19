"""
CE / PE Strategy State Machine
────────────────────────────────
Implements the pyramid entry/exit logic from CLAUDE.md Section 2.

States:
  IDLE          → Waiting for Level 1 trigger
  L1_ENTERED    → 1 lot open, strike locked
  L2_ENTERED    → 2 lots open, same strike
  L3_ENTERED    → 3 lots open, SL now active
  BLOCKED       → Target/SL hit at a level — no more entries from that level today

Each side (CE, PE) has its OWN independent instance of this state machine.
"""

from enum import Enum
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger


class State(str, Enum):
    IDLE = "IDLE"
    L1_ENTERED = "L1_ENTERED"
    L2_ENTERED = "L2_ENTERED"
    L3_ENTERED = "L3_ENTERED"
    BLOCKED = "BLOCKED"


@dataclass
class StateMachine:
    side: str  # "CE" or "PE"

    # Current state
    state: State = State.IDLE

    # Position tracking
    lots: int = 0                              # Current total lots open
    locked_strike: Optional[int] = None       # Locked at L1 — never changes
    locked_instrument: Optional[str] = None   # Full symbol e.g. NIFTY11JUN2524150PE
    locked_expiry: Optional[object] = None    # datetime.date

    # Price tracking
    entry_avg_price: Optional[Decimal] = None  # Average entry price across all entries
    total_invested: Decimal = Decimal("0")     # sum of (price × qty) for avg calculation
    total_qty: int = 0                         # total quantity bought
    level3_entry_price: Optional[Decimal] = None  # Price at which Level 3 was filled

    # P&L
    realized_pnl: Decimal = Decimal("0")

    # Blocked levels (levels where target was achieved today)
    blocked_levels: set = field(default_factory=set)  # e.g. {"L1", "L2"}

    # Config (injected by strategy engine)
    lot_size: int = 75
    target_points: Decimal = Decimal("20")
    sl_points: Decimal = Decimal("10")

    def reset_daily(self):
        """Reset for a new trading day. Called at 9:00 AM."""
        logger.info(f"[{self.side}] Daily reset")
        self.state = State.IDLE
        self.lots = 0
        self.locked_strike = None
        self.locked_instrument = None
        self.locked_expiry = None
        self.entry_avg_price = None
        self.level3_entry_price = None
        self.total_invested = Decimal("0")
        self.total_qty = 0
        self.realized_pnl = Decimal("0")
        self.blocked_levels = set()

    def mapped_level(self, lvl: str) -> str:
        if lvl in ("L1", "L2", "L3"):
            prefix = "S" if self.side == "CE" else "R"
            return lvl.replace("L", prefix)
        return lvl

    # ── Entry Logic ──────────────────────────────────────────────────────────

    def can_enter_level1(self) -> bool:
        """Can we enter at Level 1 (R1/S1)?"""
        if self.state != State.IDLE:
            return False
        if "L1" in self.blocked_levels:
            logger.debug(f"[{self.side}] {self.mapped_level('L1')} is blocked today")
            return False
        return True

    def can_enter_level2(self) -> bool:
        """Can we add at Level 2? Must already be at L1_ENTERED."""
        if self.state != State.L1_ENTERED:
            return False
        if "L2" in self.blocked_levels:
            logger.debug(f"[{self.side}] {self.mapped_level('L2')} is blocked today")
            return False
        return True

    def can_enter_level3(self) -> bool:
        """Can we add at Level 3? Must already be at L2_ENTERED."""
        if self.state != State.L2_ENTERED:
            return False
        if "L3" in self.blocked_levels:
            logger.debug(f"[{self.side}] {self.mapped_level('L3')} is blocked today")
            return False
        return True

    def enter_level1(self, instrument: str, strike: int, expiry, fill_price: Decimal) -> dict:
        """
        Execute Level 1 entry: buy 1 lot, lock the strike.
        Returns action details for order manager.
        """
        assert self.can_enter_level1(), f"[{self.side}] Cannot enter L1 — state={self.state}"

        qty = 1 * self.lot_size
        self.locked_strike = strike
        self.locked_instrument = instrument
        self.locked_expiry = expiry
        self.lots = 1
        self.total_qty = qty
        self.total_invested = fill_price * qty
        self.entry_avg_price = fill_price
        self.state = State.L1_ENTERED

        logger.info(
            f"[{self.side}] {self.mapped_level('L1')} ENTERED | instrument={instrument} | strike={strike} "
            f"| price={fill_price} | lots=1 | qty={qty}"
        )
        return {
            "action": "BUY",
            "level": "L1",
            "instrument": instrument,
            "strike": strike,
            "lots": 1,
            "qty": qty,
            "price": fill_price,
        }

    def enter_level2(self, fill_price: Decimal) -> dict:
        """
        Add 1 lot at Level 2. Same instrument as L1 (strike locked).
        Total = 2 lots.
        """
        assert self.can_enter_level2(), f"[{self.side}] Cannot enter L2 — state={self.state}"

        qty = 1 * self.lot_size
        self.lots = 2
        new_total_qty = self.total_qty + qty
        self.total_invested = self.total_invested + (fill_price * qty)
        self.entry_avg_price = self.total_invested / new_total_qty
        self.total_qty = new_total_qty
        self.state = State.L2_ENTERED

        logger.info(
            f"[{self.side}] {self.mapped_level('L2')} ENTERED | adding 1 lot to {self.locked_instrument} "
            f"| new_avg={self.entry_avg_price:.2f} | total_lots=2 | total_qty={self.total_qty}"
        )
        return {
            "action": "BUY",
            "level": "L2",
            "instrument": self.locked_instrument,
            "strike": self.locked_strike,
            "lots": 1,
            "qty": qty,
            "price": fill_price,
        }

    def enter_level3(self, fill_price: Decimal) -> dict:
        """
        Add 1 lot at Level 3. SL is now active.
        Total = 3 lots (MAX — hard limit per CLAUDE.md).
        """
        assert self.can_enter_level3(), f"[{self.side}] Cannot enter L3 — state={self.state}"

        qty = 1 * self.lot_size
        self.lots = 3  # MAX — hard limit
        new_total_qty = self.total_qty + qty
        self.total_invested = self.total_invested + (fill_price * qty)
        self.entry_avg_price = self.total_invested / new_total_qty
        self.level3_entry_price = fill_price
        self.total_qty = new_total_qty
        self.state = State.L3_ENTERED

        logger.info(
            f"[{self.side}] {self.mapped_level('L3')} ENTERED | adding 1 lot to {self.locked_instrument} "
            f"| new_avg={self.entry_avg_price:.2f} | total_lots=3 | SL ACTIVE @ "
            f"{self.level3_entry_price - self.sl_points:.2f}"
        )
        return {
            "action": "BUY",
            "level": "L3",
            "instrument": self.locked_instrument,
            "strike": self.locked_strike,
            "lots": 1,
            "qty": qty,
            "price": fill_price,
        }

    # ── Exit Logic ────────────────────────────────────────────────────────────

    def check_target(self, current_ltp: Decimal) -> bool:
        """
        Check if target (20 pts) has been achieved.
        Target is on TOTAL position (20 pts per lot × number of lots).
        """
        if self.state == State.IDLE or self.entry_avg_price is None:
            return False
        profit_pts = current_ltp - self.entry_avg_price
        return profit_pts >= self.target_points

    def check_sl(self, current_ltp: Decimal) -> bool:
        """
        Check if Stop Loss (10 pts) has been hit.
        SL is ONLY active at Level 3 (CLAUDE.md Rule 6).
        """
        if self.state != State.L3_ENTERED or self.level3_entry_price is None:
            return False
        loss_pts = self.level3_entry_price - current_ltp
        return loss_pts >= self.sl_points

    def exit_position(self, exit_price: Decimal, reason: str) -> dict:
        """
        Exit the ENTIRE position. Updates P&L and blocks this cycle's highest level.
        reason: "TARGET" | "SL" | "SQUAREOFF" | "MANUAL"
        """
        assert self.state not in (State.IDLE, State.BLOCKED), \
            f"[{self.side}] Nothing to exit — state={self.state}"

        pnl_pts = exit_price - self.entry_avg_price
        pnl_rupees = pnl_pts * self.total_qty
        self.realized_pnl += pnl_rupees

        # Block the highest level reached so no re-entry today
        level_map = {
            State.L1_ENTERED: "L1",
            State.L2_ENTERED: "L2",
            State.L3_ENTERED: "L3",
        }
        level_reached = level_map[self.state]
        self.blocked_levels.add(level_reached)

        result = {
            "action": "EXIT",
            "reason": reason,
            "instrument": self.locked_instrument,
            "strike": self.locked_strike,
            "lots": self.lots,
            "qty": self.total_qty,
            "exit_price": exit_price,
            "entry_avg_price": self.entry_avg_price,
            "pnl_points": pnl_pts,
            "pnl_rupees": pnl_rupees,
            "level_blocked": level_reached,
        }

        logger.info(
            f"[{self.side}] EXIT | reason={reason} | price={exit_price:.2f} "
            f"| avg_entry={self.entry_avg_price:.2f} | pnl={pnl_rupees:.2f} "
            f"| level_blocked={self.mapped_level(level_reached)}"
        )

        # Reset position state but keep blocked_levels and realized_pnl
        self.state = State.IDLE
        self.lots = 0
        self.locked_strike = None
        self.locked_instrument = None
        self.locked_expiry = None
        self.entry_avg_price = None
        self.level3_entry_price = None
        self.total_invested = Decimal("0")
        self.total_qty = 0

        return result

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self, current_ltp: Optional[Decimal] = None) -> dict:
        unrealized = None
        if current_ltp and self.entry_avg_price and self.total_qty > 0:
            unrealized = (current_ltp - self.entry_avg_price) * self.total_qty

        return {
            "side": self.side,
            "state": self.state.value,
            "lots": self.lots,
            "locked_strike": self.locked_strike,
            "locked_instrument": self.locked_instrument,
            "entry_avg_price": float(self.entry_avg_price) if self.entry_avg_price else None,
            "current_ltp": float(current_ltp) if current_ltp else None,
            "unrealized_pnl": float(unrealized) if unrealized else None,
            "realized_pnl": float(self.realized_pnl),
            "blocked_levels": list(self.blocked_levels),
        }
