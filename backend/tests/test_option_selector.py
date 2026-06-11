"""
Tests for option selector — ATM calculation, symbol generation.
"""

import pytest
from decimal import Decimal
from datetime import date
from app.core.option_selector import get_atm_strike, get_option_strike, build_option_symbol, get_option_details


class TestATMCalculation:
    def test_round_down_to_50(self):
        assert get_atm_strike(Decimal("23186")) == 23200

    def test_exact_50(self):
        assert get_atm_strike(Decimal("23200")) == 23200

    def test_round_up(self):
        assert get_atm_strike(Decimal("23225")) == 23200  # mid-point rounds down in banker's rounding
        # Let's be exact: 23225/50 = 464.5, round=464, *50=23200

    def test_round_up_above_mid(self):
        assert get_atm_strike(Decimal("23251")) == 23250

    def test_round_down_below_mid(self):
        assert get_atm_strike(Decimal("23149")) == 23150


class TestOptionStrike:
    def test_pe_strike_is_atm_plus_50(self):
        # NIFTY=23200 → ATM=23200 → PE strike=23250
        strike = get_option_strike("PE", Decimal("23200"))
        assert strike == 23250

    def test_ce_strike_is_atm_minus_50(self):
        # NIFTY=23200 → ATM=23200 → CE strike=23150
        strike = get_option_strike("CE", Decimal("23200"))
        assert strike == 23150

    def test_pe_with_non_round_nifty(self):
        # NIFTY=23186 → ATM=23200 → PE=23250
        strike = get_option_strike("PE", Decimal("23186"))
        assert strike == 23250

    def test_ce_with_non_round_nifty(self):
        # NIFTY=23186 → ATM=23200 → CE=23150
        strike = get_option_strike("CE", Decimal("23186"))
        assert strike == 23150

    def test_invalid_side_raises(self):
        with pytest.raises(ValueError):
            get_option_strike("XX", Decimal("23200"))


class TestSymbolBuilding:
    def test_pe_symbol(self):
        expiry = date(2024, 6, 13)
        symbol = build_option_symbol("PE", 23250, expiry)
        assert symbol == "NIFTY13JUN2423250PE"

    def test_ce_symbol(self):
        expiry = date(2024, 6, 27)
        symbol = build_option_symbol("CE", 23150, expiry)
        assert symbol == "NIFTY27JUN2423150CE"

    def test_symbol_uppercase(self):
        expiry = date(2024, 6, 13)
        symbol = build_option_symbol("PE", 23250, expiry)
        assert symbol == symbol.upper()


class TestGetOptionDetails:
    def test_full_details_pe(self):
        details = get_option_details("PE", Decimal("23186"), trade_date=date(2024, 6, 13))
        assert details["side"] == "PE"
        assert details["strike"] == 23250  # ATM(23200) + 50
        assert "NIFTY" in details["symbol"]
        assert "PE" in details["symbol"]
        assert details["expiry"] == date(2024, 6, 13)

    def test_tuesday_rule_in_option_details(self):
        """Tuesday should get next weekly expiry."""
        tuesday = date(2024, 6, 11)
        details = get_option_details("PE", Decimal("23200"), trade_date=tuesday)
        expected_expiry = date(2024, 6, 20)  # Next Thursday
        assert details["expiry"] == expected_expiry
