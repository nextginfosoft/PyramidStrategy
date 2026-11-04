"""
Weekly expiry selection around NSE holidays that fall on a Tuesday.

Bug: on Tue 3 Nov 2026 the engine asked Kite for NIFTY26N1023700PE (expiry Tue 10 Nov).
10 Nov is a holiday, so NSE pre-pones that week's expiry to Mon 9 Nov and the contract
does not exist ("instrument has either expired or does not exist"). get_expiry_date only
handled a holiday Tuesday when *today* was the Monday before it; on every earlier day of
that week it returned the holiday itself.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.option_selector import build_option_symbol, get_option_details
from app.core.time_rules import (
    TUESDAY_HOLIDAYS,
    format_expiry_for_symbol,
    get_expiry_date,
)


def legacy_expiry(d: date) -> date:
    """The previous implementation, kept to prove nothing changes outside holiday weeks."""
    days_to_tuesday = (1 - d.weekday()) % 7
    if d.weekday() == 1:
        return d + timedelta(days=7)
    if d.weekday() == 0 and (d + timedelta(days=1)) in TUESDAY_HOLIDAYS:
        return d + timedelta(days=8)
    if days_to_tuesday == 0:
        days_to_tuesday = 7
    return d + timedelta(days=days_to_tuesday)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


class TestTheFailingCase:
    def test_the_exact_contract_that_was_rejected_is_no_longer_selected(self):
        details = get_option_details("PE", Decimal("23660.05"), date(2026, 11, 3))
        assert details["symbol"] != "NIFTY26N1023700PE"
        assert details["expiry"] == date(2026, 11, 9)
        assert details["symbol"] == "NIFTY26N0923700PE"

    @pytest.mark.parametrize("day", [date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 6)])
    def test_the_whole_week_before_the_diwali_holiday_uses_the_monday_contract(self, day):
        assert get_expiry_date(day) == date(2026, 11, 9)

    def test_on_the_pre_poned_monday_it_rolls_to_the_next_week(self):
        assert get_expiry_date(date(2026, 11, 9)) == date(2026, 11, 17)

    def test_the_week_after_the_holiday_is_normal_again(self):
        for day in (date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 13), date(2026, 11, 16)):
            assert get_expiry_date(day) == date(2026, 11, 17)


class TestEveryHolidayWeek:
    @pytest.mark.parametrize("holiday", sorted(TUESDAY_HOLIDAYS))
    def test_days_before_a_tuesday_holiday_use_the_preponed_monday(self, holiday):
        monday = holiday - timedelta(days=1)
        # previous Tuesday (a normal expiry day) through the Friday before the holiday week's Monday
        for d in daterange(holiday - timedelta(days=7), holiday - timedelta(days=2)):
            assert get_expiry_date(d) == monday, d

    @pytest.mark.parametrize("holiday", sorted(TUESDAY_HOLIDAYS))
    def test_on_the_preponed_monday_the_next_weeks_contract_is_used(self, holiday):
        monday = holiday - timedelta(days=1)
        assert get_expiry_date(monday) == holiday + timedelta(days=7)


class TestProperties:
    def test_never_a_holiday_never_a_weekend_always_in_the_future(self):
        for d in daterange(date(2025, 1, 1), date(2027, 12, 31)):
            e = get_expiry_date(d)
            assert e not in TUESDAY_HOLIDAYS, (d, e)
            assert e.weekday() < 5, (d, e)
            assert e > d, (d, e)

    def test_never_more_than_eight_days_ahead(self):
        for d in daterange(date(2025, 1, 1), date(2027, 12, 31)):
            assert (get_expiry_date(d) - d).days <= 8, d

    def test_never_goes_backwards_as_the_date_advances(self):
        prev = get_expiry_date(date(2025, 1, 1))
        for d in daterange(date(2025, 1, 2), date(2027, 12, 31)):
            cur = get_expiry_date(d)
            assert cur >= prev, d
            prev = cur


class TestNothingChangesOutsideHolidayWeeks:
    def test_identical_to_the_previous_behaviour_everywhere_a_holiday_is_not_involved(self):
        affected = set()
        for h in TUESDAY_HOLIDAYS:
            affected.update(daterange(h - timedelta(days=8), h + timedelta(days=1)))
        checked = 0
        for d in daterange(date(2025, 1, 1), date(2027, 12, 31)):
            if d in affected:
                continue
            assert get_expiry_date(d) == legacy_expiry(d), d
            checked += 1
        assert checked > 1000

    def test_the_old_bug_is_exactly_what_changed(self):
        """Inside the holiday windows the old code returned the holiday (or was right only by luck)."""
        for h in TUESDAY_HOLIDAYS:
            assert legacy_expiry(h - timedelta(days=4)) == h  # old: a contract that does not exist
            assert get_expiry_date(h - timedelta(days=4)) == h - timedelta(days=1)


class TestSymbolFormat:
    @pytest.mark.parametrize("expiry, expected", [
        (date(2026, 10, 27), "26OCT"),   # last expiry of October -> monthly format
        (date(2026, 11, 3), "26N03"),
        (date(2026, 11, 9), "26N09"),    # pre-poned weekly
        (date(2026, 11, 17), "26N17"),
        (date(2026, 11, 23), "26NOV"),   # monthly expiry pre-poned from the 24 Nov holiday
        (date(2026, 12, 1), "26D01"),
        (date(2026, 6, 30), "26JUN"),
        (date(2026, 3, 2), "26302"),     # Holi week: weekly, pre-poned from Tue 3 Mar
        (date(2026, 3, 30), "26MAR"),    # monthly, pre-poned from the 31 Mar holiday
    ])
    def test_weekly_vs_monthly_format(self, expected, expiry):
        assert format_expiry_for_symbol(expiry) == expected

    def test_a_preponed_monthly_contract_builds_the_monthly_symbol(self):
        expiry = get_expiry_date(date(2026, 11, 18))
        assert expiry == date(2026, 11, 23)
        assert build_option_symbol("CE", 23400, expiry) == "NIFTY26NOV23400CE"
