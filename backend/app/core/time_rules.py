"""
Time Rules — Phase 1
─────────────────────
IST timezone utilities and strategy time-based rules.

Hard-coded rules (CLAUDE.md Section 2.3):
  - No fresh entries after 11:15 AM IST
  - All positions squared off at 11:30 AM IST
  - Tuesday: use NEXT weekly expiry (Thursday) instead of same-day
  - Other days: use nearest upcoming Thursday as expiry
"""

from datetime import date, datetime, time, timedelta
from typing import Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Strategy time constants
ENTRY_CUTOFF = time(11, 15)   # No new entries after 11:15 AM IST
SQUAREOFF_TIME = time(11, 30) # Force close all at 11:30 AM IST
MARKET_OPEN = time(9, 15)     # NSE opens at 9:15 AM IST


def now_ist() -> datetime:
    """Current datetime in IST."""
    import os
    dt = datetime.now(IST)
    mock_time_str = os.getenv("MOCK_TIME")
    if mock_time_str:
        try:
            # Format: "HH:MM"
            h, m = map(int, mock_time_str.split(":"))
            dt = dt.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            pass
    return dt


def today_ist() -> date:
    """Current date in IST."""
    return now_ist().date()


def is_entry_allowed(current_time: Optional[datetime] = None) -> bool:
    """
    Returns True if new entries are allowed (before 11:15 AM IST).
    Hard rule — never configurable.
    """
    t = current_time or now_ist()
    return t.time() < ENTRY_CUTOFF


def is_squareoff_time(current_time: Optional[datetime] = None) -> bool:
    """
    Returns True if it's past 11:30 AM IST — all positions must be closed.
    Hard rule — never configurable.
    """
    t = current_time or now_ist()
    return t.time() >= SQUAREOFF_TIME


# Alias used in tests and strategy engine
should_squareoff = is_squareoff_time


def is_tuesday(d: Optional[date] = None) -> bool:
    """
    Returns True if the given date (or today) is Tuesday.
    Tuesday Rule: use next weekly expiry instead of current-week expiry.
    """
    check_date = d or today_ist()
    return check_date.weekday() == 1  # Monday=0, Tuesday=1


def get_next_thursday(from_date: Optional[date] = None) -> date:
    """
    Returns the next Thursday strictly after the given date (or today).
    NIFTY weekly options expire on Thursday.
    """
    d = from_date or today_ist()
    days_until_thursday = (3 - d.weekday()) % 7  # Thursday = weekday 3
    if days_until_thursday == 0:
        days_until_thursday = 7  # Already Thursday — go to next week
    return d + timedelta(days=days_until_thursday)


def get_expiry_date(trade_date: Optional[date] = None) -> date:
    """
    Returns the correct expiry date for options:
    - Thursday → same day (it IS the weekly expiry)
    - Tuesday  → skip this week's Thursday, use NEXT Thursday (Tuesday Rule)
    - All other days → nearest upcoming Thursday (same week)

    This is a hard rule — NEVER make it configurable.
    """
    d = trade_date or today_ist()
    days_to_thursday = (3 - d.weekday()) % 7  # Thursday = weekday 3

    if is_tuesday(d):
        # Tuesday Rule: jump over current week's Thursday to next week
        days_to_thursday += 7

    return d + timedelta(days=days_to_thursday)


def format_expiry_for_symbol(expiry: date) -> str:
    """
    Formats expiry date in Kite's instrument symbol format.
    - Monthly expiry (last Thursday of the month): '27JUN24' (DDMMMYY)
    - Weekly expiry (other Thursdays): '24606' (YYMDD where M is 1-9, O, N, D)
    """
    # Check if this Thursday is the last Thursday of the month
    next_thursday = expiry + timedelta(days=7)
    is_monthly = next_thursday.month != expiry.month

    if is_monthly:
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
            5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
            9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
        }
        return f"{expiry.day:02d}{month_map[expiry.month]}{str(expiry.year)[2:]}"
    else:
        # Weekly expiry format: YY + M + DD
        yy = str(expiry.year)[2:]
        month_char_map = {
            1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
            7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D"
        }
        m = month_char_map[expiry.month]
        dd = f"{expiry.day:02d}"
        return f"{yy}{m}{dd}"


def seconds_until_squareoff(current_time: Optional[datetime] = None) -> int:
    """Returns seconds remaining until 11:30 AM squareoff. Negative if past."""
    t = current_time or now_ist()
    squareoff = t.replace(hour=11, minute=30, second=0, microsecond=0)
    return int((squareoff - t).total_seconds())
