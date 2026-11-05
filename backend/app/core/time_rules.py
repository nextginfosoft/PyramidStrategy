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

def to_ist_str(dt: Optional[datetime], fmt: str = "%I:%M %p") -> str:
    """Convert UTC or naive datetime to IST formatted string."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(IST).strftime(fmt)

# Strategy time constants
MARKET_OPEN = time(9, 15)     # NSE opens at 9:15 AM IST


def get_time_from_str(t_str: str) -> time:
    """Parse time from 'HH:MM' string."""
    h, m = map(int, t_str.split(":"))
    return time(h, m)


def get_entry_cutoff_time(squareoff_time_str: str, no_entry_time_str: Optional[str] = None) -> time:
    """
    Get entry cutoff time.

    If the user configured an explicit no-entry time, that is the cutoff (never later
    than square-off time itself). Otherwise it is 15 minutes prior to square-off time.
    """
    if no_entry_time_str:
        return min(get_time_from_str(no_entry_time_str), get_time_from_str(squareoff_time_str))
    h, m = map(int, squareoff_time_str.split(":"))
    dt = datetime.combine(date.min, time(h, m)) - timedelta(minutes=15)
    return dt.time()


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


def is_entry_allowed(
    current_time: Optional[datetime] = None,
    squareoff_time_str: str = "11:30",
    no_entry_time_str: Optional[str] = None,
) -> bool:
    """
    Returns True if new entries are allowed (before the calculated entry cutoff).

    With a user-configured no-entry time, that time alone decides (clamped to the
    square-off time). Without one, keeps the legacy rule: 15 minutes before
    square-off, and never after 2:30 PM (14:30) IST.
    """
    t = current_time or now_ist()
    if no_entry_time_str:
        return t.time() < get_entry_cutoff_time(squareoff_time_str, no_entry_time_str)
    if t.time() >= time(14, 30):
        return False
    cutoff = get_entry_cutoff_time(squareoff_time_str)
    return t.time() < cutoff


def is_squareoff_time(current_time: Optional[datetime] = None, squareoff_time_str: str = "11:30") -> bool:
    """
    Returns True if it's past/at square-off time IST — all positions must be closed.
    """
    t = current_time or now_ist()
    sq_time = get_time_from_str(squareoff_time_str)
    return t.time() >= sq_time


# Alias used in tests and strategy engine
should_squareoff = is_squareoff_time


def is_tuesday(d: Optional[date] = None) -> bool:
    """
    Returns True if the given date (or today) is Tuesday.
    Tuesday Rule: use next weekly expiry instead of current-week expiry.
    """
    check_date = d or today_ist()
    return check_date.weekday() == 1  # Monday=0, Tuesday=1


def get_next_tuesday(from_date: Optional[date] = None) -> date:
    """
    Returns the next Tuesday strictly after the given date (or today).
    NIFTY weekly options expire on Tuesday.
    """
    d = from_date or today_ist()
    days_until_tuesday = (1 - d.weekday()) % 7  # Tuesday = weekday 1
    if days_until_tuesday == 0:
        days_until_tuesday = 7  # Already Tuesday — go to next week
    return d + timedelta(days=days_until_tuesday)


# NSE trading holidays that fall on a Tuesday. NIFTY weekly options normally expire on
# Tuesday; when NSE is closed that day, the expiry moves to the previous trading day.
TUESDAY_HOLIDAYS = {
    date(2026, 3, 3),   # Holi
    date(2026, 3, 31),  # Shri Mahavir Jayanti
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 10), # Diwali-Balipratipada
    date(2026, 11, 24), # Prakash Gurpurab Sri Guru Nanak Dev
}


def _weekly_expiry_for(tuesday: date) -> date:
    """The actual expiry date of the weekly contract whose normal expiry is `tuesday`:
    the Tuesday itself, or the previous trading day when NSE is closed that Tuesday."""
    expiry = tuesday
    while expiry in TUESDAY_HOLIDAYS or expiry.weekday() >= 5:
        expiry -= timedelta(days=1)
    return expiry


def get_expiry_date(trade_date: Optional[date] = None) -> date:
    """
    Returns the correct expiry date for options:
    - On a weekly expiry day (Tuesday, or the previous trading day when that
      Tuesday is an NSE holiday) -> roll over to the NEXT weekly expiry contract.
    - On every other day -> the nearest upcoming weekly expiry contract, which is the
      pre-poned date when the coming Tuesday is an NSE holiday (so a contract that
      Kite does not list is never selected in the days leading up to that holiday).

    This is a hard rule — NEVER make it configurable.
    """
    d = trade_date or today_ist()

    tuesday = d + timedelta(days=(1 - d.weekday()) % 7)  # this week's Tuesday (today if Tuesday)
    expiry = _weekly_expiry_for(tuesday)
    if d >= expiry:
        # Today is (or is past) this week's expiry day: trade next week's contract
        expiry = _weekly_expiry_for(tuesday + timedelta(days=7))
    return expiry


def format_expiry_for_symbol(expiry: date) -> str:
    """
    Formats expiry date in Kite's instrument symbol format.
    - Monthly expiry (the last weekly expiry of the month, even when pre-poned
      for a holiday): '24JUN' (YYMMM)
    - Weekly expiry (all others): '24606' (YYMDD where M is 1-9, O, N, D)
    """
    # The contract is monthly when the following week's expiry falls in the next month
    tuesday = expiry + timedelta(days=(1 - expiry.weekday()) % 7)
    following_expiry = _weekly_expiry_for(tuesday + timedelta(days=7))
    is_monthly = following_expiry.month != expiry.month

    if is_monthly:
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
            5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
            9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
        }
        return f"{str(expiry.year)[2:]}{month_map[expiry.month]}"
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


def seconds_until_squareoff(current_time: Optional[datetime] = None, squareoff_time_str: str = "11:30") -> int:
    """Returns seconds remaining until configured square-off time. Negative if past."""
    t = current_time or now_ist()
    h, m = map(int, squareoff_time_str.split(":"))
    squareoff = t.replace(hour=h, minute=m, second=0, microsecond=0)
    return int((squareoff - t).total_seconds())
