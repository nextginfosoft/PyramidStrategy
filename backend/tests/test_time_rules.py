"""
Tests for all time-based rules (Rules 7, 8, 9 from CLAUDE.md)
"""

import pytest
from datetime import date, datetime
import pytz
from app.core.time_rules import (
    is_entry_allowed, should_squareoff, is_tuesday,
    get_expiry_date, format_expiry_for_symbol, get_next_thursday
)

IST = pytz.timezone("Asia/Kolkata")


def make_ist_time(hour: int, minute: int, day_of_week: int = 3) -> datetime:
    """Create an IST datetime for a specific weekday (0=Mon, 3=Thu)."""
    # Use a known date: Jun 10, 2024 is Monday
    base = date(2024, 6, 10)
    from datetime import timedelta
    target = base + timedelta(days=day_of_week)
    dt = datetime(target.year, target.month, target.day, hour, minute, 0)
    return IST.localize(dt)


class TestEntryAllowed:
    def test_entry_allowed_at_9am(self):
        t = make_ist_time(9, 0)
        assert is_entry_allowed(t) is True

    def test_entry_allowed_at_1100(self):
        t = make_ist_time(11, 0)
        assert is_entry_allowed(t) is True

    def test_entry_allowed_at_1114(self):
        t = make_ist_time(11, 14)
        assert is_entry_allowed(t) is True

    def test_entry_blocked_at_1115(self):
        """Rule 8: No fresh entries at exactly 11:15 AM."""
        t = make_ist_time(11, 15)
        assert is_entry_allowed(t) is False

    def test_entry_blocked_at_1130(self):
        t = make_ist_time(11, 30)
        assert is_entry_allowed(t) is False

    def test_entry_blocked_after_1115(self):
        t = make_ist_time(11, 45)
        assert is_entry_allowed(t) is False


class TestSquareoff:
    def test_no_squareoff_at_1000(self):
        t = make_ist_time(10, 0)
        assert should_squareoff(t) is False

    def test_no_squareoff_at_1129(self):
        t = make_ist_time(11, 29)
        assert should_squareoff(t) is False

    def test_squareoff_at_1130(self):
        """Rule 7: Squareoff at exactly 11:30 AM."""
        t = make_ist_time(11, 30)
        assert should_squareoff(t) is True

    def test_squareoff_after_1130(self):
        t = make_ist_time(12, 0)
        assert should_squareoff(t) is True


class TestTuesdayRule:
    def test_monday_is_not_tuesday(self):
        monday = date(2024, 6, 10)
        assert is_tuesday(monday) is False

    def test_tuesday_detected(self):
        tuesday = date(2024, 6, 11)
        assert is_tuesday(tuesday) is True

    def test_thursday_is_not_tuesday(self):
        thursday = date(2024, 6, 13)
        assert is_tuesday(thursday) is False


class TestExpiryDate:
    def test_thursday_expiry_is_same_day(self):
        """On Thursday, expiry should be today (same-day weekly expiry)."""
        thursday = date(2024, 6, 13)
        expiry = get_expiry_date(thursday)
        assert expiry == thursday

    def test_monday_expiry_is_this_thursday(self):
        """On Monday, expiry should be this week's Thursday."""
        monday = date(2024, 6, 10)
        expiry = get_expiry_date(monday)
        expected = date(2024, 6, 13)  # Thursday of same week
        assert expiry == expected

    def test_tuesday_expiry_is_next_thursday(self):
        """Rule 9: Tuesday → next weekly expiry (next Thursday)."""
        tuesday = date(2024, 6, 11)
        expiry = get_expiry_date(tuesday)
        expected = date(2024, 6, 20)  # NEXT Thursday
        assert expiry == expected, f"Expected {expected}, got {expiry}"

    def test_wednesday_expiry_is_this_thursday(self):
        wednesday = date(2024, 6, 12)
        expiry = get_expiry_date(wednesday)
        expected = date(2024, 6, 13)
        assert expiry == expected

    def test_friday_expiry_is_next_thursday(self):
        friday = date(2024, 6, 14)
        expiry = get_expiry_date(friday)
        expected = date(2024, 6, 20)
        assert expiry == expected


class TestSymbolFormat:
    def test_expiry_format(self):
        d = date(2024, 6, 27)
        assert format_expiry_for_symbol(d) == "27JUN24"

    def test_expiry_format_single_digit_day(self):
        d = date(2024, 6, 6)
        assert format_expiry_for_symbol(d) == "24606"
