"""BANKNIFTY / instrument registry tests (Phase 1)."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.instruments import get_instrument, instrument_from_symbol
from app.core.option_selector import (
    estimate_option_price, get_atm_strike, get_instrument_expiry,
    get_option_details, get_option_strike, build_option_symbol,
)
from app.core.time_rules import get_monthly_expiry_date, format_expiry_for_symbol


class TestRegistry:
    def test_default_is_nifty(self):
        assert get_instrument().name == "NIFTY"

    def test_case_insensitive(self):
        assert get_instrument("banknifty").spot_token == 260105

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_instrument("FINNIFTY")

    def test_banknifty_is_paper_only(self):
        assert get_instrument("BANKNIFTY").paper_only
        assert not get_instrument("NIFTY").paper_only

    def test_instrument_from_symbol(self):
        assert instrument_from_symbol("BANKNIFTY26OCT55000CE").name == "BANKNIFTY"
        assert instrument_from_symbol("NIFTY26O0623150PE").name == "NIFTY"


class TestBankNiftyStrikes:
    def test_atm_rounds_to_100(self):
        assert get_atm_strike(Decimal("55040"), "BANKNIFTY") == 55000
        assert get_atm_strike(Decimal("55060"), "BANKNIFTY") == 55100

    def test_pe_is_atm_plus_100(self):
        assert get_option_strike("PE", Decimal("55040"), "BANKNIFTY") == 55100

    def test_ce_is_atm_minus_100(self):
        assert get_option_strike("CE", Decimal("55040"), "BANKNIFTY") == 54900

    def test_nifty_unchanged(self):
        assert get_option_strike("PE", Decimal("23186")) == 23250
        assert get_option_strike("CE", Decimal("23186")) == 23150


class TestBankNiftyExpiry:
    def test_mid_month_uses_last_tuesday(self):
        assert get_monthly_expiry_date(date(2026, 10, 5)) == date(2026, 10, 27)

    def test_expiry_day_rolls_to_next_month(self):
        assert get_monthly_expiry_date(date(2026, 10, 27)) == date(2026, 11, 23)  # Tue 24 Nov is a holiday → Mon 23

    def test_holiday_tuesday_shifts_to_monday(self):
        # 31 Mar 2026 is a Tuesday holiday → expiry Monday 30 Mar
        assert get_monthly_expiry_date(date(2026, 3, 10)) == date(2026, 3, 30)

    def test_december_rolls_into_january(self):
        assert get_monthly_expiry_date(date(2026, 12, 30)).year == 2027

    def test_instrument_expiry_dispatch(self):
        d = date(2026, 10, 5)  # Monday
        assert get_instrument_expiry("BANKNIFTY", d) == date(2026, 10, 27)
        assert get_instrument_expiry("NIFTY", d) == date(2026, 10, 6)


class TestBankNiftySymbol:
    def test_monthly_symbol_format(self):
        sym = build_option_symbol("CE", 55000, date(2026, 10, 27), "BANKNIFTY")
        assert sym == "BANKNIFTY26OCT55000CE"

    def test_shifted_monday_expiry_still_monthly_format(self):
        # Monday 30 Mar 2026 is not a "last Tuesday" — must not fall to weekly format
        assert format_expiry_for_symbol(date(2026, 3, 30), monthly=True) == "26MAR"
        sym = build_option_symbol("PE", 52000, date(2026, 3, 30), "BANKNIFTY")
        assert sym == "BANKNIFTY26MAR52000PE"

    def test_option_details(self):
        d = get_option_details("PE", Decimal("55040"), date(2026, 10, 5), "BANKNIFTY")
        assert d["symbol"] == "BANKNIFTY26OCT55100PE"
        assert d["strike"] == 55100
        assert d["expiry"] == date(2026, 10, 27)


class TestEstimator:
    def test_banknifty_atm_uses_larger_time_value(self):
        bn = estimate_option_price("BANKNIFTY26OCT55000CE", Decimal("55000"))
        assert bn == Decimal("200.00")

    def test_nifty_unchanged(self):
        assert estimate_option_price("NIFTY26O0623200CE", Decimal("23200")) == Decimal("80.00")
