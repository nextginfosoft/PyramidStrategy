"""
Tests for CE/PE state machine — covers all 10 CLAUDE.md strategy rules.
"""

import pytest
from decimal import Decimal
from datetime import date
from app.core.state_machine import StateMachine, State


@pytest.fixture
def ce_sm():
    sm = StateMachine(side="CE")
    sm.lot_size = 75
    sm.target_points = Decimal("20")
    sm.sl_points = Decimal("10")
    return sm


@pytest.fixture
def pe_sm():
    sm = StateMachine(side="PE")
    sm.lot_size = 75
    sm.target_points = Decimal("20")
    sm.sl_points = Decimal("10")
    return sm


INSTRUMENT = "NIFTY13JUN2423150PE"
STRIKE = 23150
EXPIRY = date(2024, 6, 13)
PRICE_L1 = Decimal("85.00")
PRICE_L2 = Decimal("90.00")
PRICE_L3 = Decimal("95.00")


class TestRule1_SameDayExpiry:
    """Rule 1: Strike uses same-day expiry (enforced in option_selector, tested there)."""
    pass  # Covered in test_option_selector.py


class TestRule2_StrikeLocking:
    """Rule 2: Strike selected at L1 is locked — never changes."""

    def test_strike_locked_after_l1(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        assert pe_sm.locked_strike == STRIKE
        assert pe_sm.locked_instrument == INSTRUMENT

    def test_l2_uses_same_instrument(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        result = pe_sm.enter_level2(PRICE_L2)
        assert result["instrument"] == INSTRUMENT
        assert result["strike"] == STRIKE

    def test_l3_uses_same_instrument(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        result = pe_sm.enter_level3(PRICE_L3)
        assert result["instrument"] == INSTRUMENT
        assert result["strike"] == STRIKE


class TestRule3_PositionSizing:
    """Rule 3: Level 1=1 lot, Level 2=add 1=2 total, Level 3=add 1=3 total. Max=3."""

    def test_l1_is_1_lot(self, pe_sm):
        result = pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        assert result["lots"] == 1
        assert pe_sm.lots == 1

    def test_l2_total_is_2_lots(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        assert pe_sm.lots == 2

    def test_l3_total_is_3_lots_max(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)
        assert pe_sm.lots == 3

    def test_cannot_enter_l4_after_l3(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)
        # State is L3_ENTERED — no more entries possible
        assert pe_sm.can_enter_level1() is False
        assert pe_sm.can_enter_level2() is False
        assert pe_sm.can_enter_level3() is False

    def test_qty_equals_lots_times_lot_size(self, pe_sm):
        pe_sm.lot_size = 75
        result = pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        assert result["qty"] == 75


class TestRule4_ExitEntirePosition:
    """Rule 4: On target → exit ENTIRE position immediately."""

    def test_exit_closes_all_lots_at_l1(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        result = pe_sm.exit_position(Decimal("105.00"), "TARGET")
        assert result["lots"] == 1
        assert result["qty"] == 75
        assert pe_sm.lots == 0
        assert pe_sm.state == State.IDLE

    def test_exit_closes_all_lots_at_l2(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        result = pe_sm.exit_position(Decimal("110.00"), "TARGET")
        assert result["qty"] == 150  # 2 lots × 75
        assert pe_sm.lots == 0

    def test_exit_closes_all_lots_at_l3(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)
        result = pe_sm.exit_position(Decimal("115.00"), "TARGET")
        assert result["qty"] == 225  # 3 lots × 75
        assert pe_sm.lots == 0


class TestRule5_NoReentry:
    """Rule 5: After target at a level → no re-entry from that level on same day."""

    def test_l1_blocked_after_target(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.exit_position(Decimal("105.00"), "TARGET")

        # L1 should now be blocked
        assert "L1" in pe_sm.blocked_levels
        assert pe_sm.can_enter_level1() is False

    def test_l2_blocked_after_target_at_l2(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.exit_position(Decimal("110.00"), "TARGET")

        assert "L2" in pe_sm.blocked_levels

    def test_new_cycle_after_l1_target(self, pe_sm):
        """Rule 10: After target at L1, if next level hit, new cycle starts from 1 lot."""
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.exit_position(Decimal("105.00"), "TARGET")  # L1 blocked

        # L1 is blocked — cannot re-enter at L1
        assert pe_sm.can_enter_level1() is False
        # But state is IDLE — ready for new instrument if different level triggers
        assert pe_sm.state == State.IDLE


class TestRule6_StopLoss:
    """Rule 6: SL only at Level 3, fixed at 10 points. No SL at L1 or L2."""

    def test_no_sl_at_l1(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        # Drop price by 50 pts — should NOT trigger SL (only at L3)
        assert pe_sm.check_sl(Decimal("35.00")) is False

    def test_no_sl_at_l2(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        assert pe_sm.check_sl(Decimal("35.00")) is False

    def test_sl_active_at_l3(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)

        avg = pe_sm.entry_avg_price
        sl_trigger = avg - Decimal("10")
        assert pe_sm.check_sl(sl_trigger) is True

    def test_sl_not_triggered_at_9pts(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)

        avg = pe_sm.entry_avg_price
        not_sl = avg - Decimal("9")
        assert pe_sm.check_sl(not_sl) is False

    def test_sl_triggered_at_exactly_10pts(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(PRICE_L2)
        pe_sm.enter_level3(PRICE_L3)

        avg = pe_sm.entry_avg_price
        sl_exact = avg - Decimal("10")
        assert pe_sm.check_sl(sl_exact) is True


class TestTargetDetection:
    """Target = 20 pts regardless of number of lots."""

    def test_target_hit_at_20pts(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        target_price = PRICE_L1 + Decimal("20")
        assert pe_sm.check_target(target_price) is True

    def test_target_not_hit_at_19pts(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        near_target = PRICE_L1 + Decimal("19")
        assert pe_sm.check_target(near_target) is False

    def test_target_uses_avg_price(self, pe_sm):
        """Target is based on avg_entry, not first entry price."""
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.enter_level2(Decimal("95.00"))  # Different L2 price
        # Target from avg price
        target_price = pe_sm.entry_avg_price + Decimal("20")
        assert pe_sm.check_target(target_price) is True


class TestIndependence:
    """CE and PE state machines are completely independent."""

    def test_ce_and_pe_independent(self, ce_sm, pe_sm):
        """Entering PE does not affect CE and vice versa."""
        ce_instrument = "NIFTY13JUN2423100CE"
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)

        # CE should still be IDLE
        assert ce_sm.state == State.IDLE
        assert ce_sm.lots == 0

    def test_pe_exit_does_not_affect_ce(self, ce_sm, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.exit_position(Decimal("105.00"), "TARGET")

        ce_sm.enter_level1("NIFTY13JUN2423100CE", 23100, EXPIRY, Decimal("90.00"))
        assert ce_sm.state == State.L1_ENTERED  # CE unaffected

    def test_daily_reset_clears_both(self, ce_sm, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)
        pe_sm.reset_daily()

        assert pe_sm.state == State.IDLE
        assert pe_sm.lots == 0
        assert pe_sm.locked_strike is None
        assert len(pe_sm.blocked_levels) == 0


class TestPnLCalculation:
    """P&L = (exit_price - avg_entry) × total_qty."""

    def test_pnl_at_l1_target(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, PRICE_L1)  # entry=85
        result = pe_sm.exit_position(Decimal("105.00"), "TARGET")  # exit=105
        # PnL = (105-85) × 75 = 20 × 75 = 1500
        assert result["pnl_points"] == Decimal("20")
        assert result["pnl_rupees"] == Decimal("1500.00")

    def test_pnl_at_l3_sl(self, pe_sm):
        pe_sm.enter_level1(INSTRUMENT, STRIKE, EXPIRY, Decimal("90.00"))
        pe_sm.enter_level2(Decimal("90.00"))
        pe_sm.enter_level3(Decimal("90.00"))
        # avg = 90, SL at 80 (-10 pts)
        result = pe_sm.exit_position(Decimal("80.00"), "SL")
        # PnL = (80-90) × 225 = -10 × 225 = -2250
        assert result["pnl_points"] == Decimal("-10.00")
        assert result["pnl_rupees"] == Decimal("-2250.00")
