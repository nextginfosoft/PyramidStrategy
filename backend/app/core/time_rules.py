"""
Time Rules Engine
─────────────────
Enforces all time-based rules from CLAUDE.md:
  Rule 7: Square-off all positions by 11:30 AM IST
  Rule 8: No fresh entries after 11:15 AM IST
  Rule 9: Tuesday → use next weekly expiry instead of same-day expiry
"""

from datetime import datetime, date, timedelta
import pytz
from loguru import logger


IST = pytz.timezone("Asia/Kolkata")

# Hard-coded per CLAUDE.md — never make configurable
ENTRY_CUTOFF_HOUR = 11
ENTRY_CUTOFF_MINUTE = 15
SQUAREOFF_HOUR = 11
SQUAREOFF_MINUTE = 30


def now_ist() -> datetime:
    """Current time in IST."""
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def is_entry_allowed(current_time: datetime | None = None) -> bool:
    """
    Returns False if current IST time is at or past 11:15 AM.
    Rule 8: No fresh entries after 11:15 AM IST.
    """
    t = current_time or now_ist()
    if t.tzinfo is None:
        t = IST.localize(t)
    cutoff = t.replace(hour=ENTRY_CUTOFF_HOUR, minute=ENTRY_CUTOFF_MINUTE, second=0, microsecond=0)
    allowed = t < cutoff
    if not allowed:
        logger.debug(f"Entry blocked: current time {t.strftime('%H:%M:%S')} >= 11:15 AM IST")
    return allowed


def should_squareoff(current_time: datetime | None = None) -> bool:
    """
    Returns True if current IST time is at or past 11:30 AM.
    Rule 7: All positions must be squared off by 11:30 AM IST.
    """
    t = current_time or now_ist()
    if t.tzinfo is None:
        t = IST.localize(t)
    squareoff_time = t.replace(hour=SQUAREOFF_HOUR, minute=SQUAREOFF_MINUTE, second=0, microsecond=0)
    return t >= squareoff_time


def is_tuesday(trade_date: date | None = None) -> bool:
    """Returns True if given date (or today) is a Tuesday."""
    d = trade_date or today_ist()
    return d.weekday() == 1  # Monday=0, Tuesday=1


def get_next_thursday(from_date: date) -> date:
    """Get the next Thursday on or after from_date."""
    days_ahead = 3 - from_date.weekday()  # Thursday = weekday 3
    if days_ahead < 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def get_expiry_date(trade_date: date | None = None) -> date:
    """
    Rule 9: Tuesday → next weekly expiry (next Thursday).
            Any other day → same-day expiry (if today is Thursday = weekly expiry).

    NIFTY weekly options expire every Thursday.
    If today IS Thursday, same-day expiry = today's weekly expiry.
    """
    d = trade_date or today_ist()

    if is_tuesday(d):
        # Use NEXT weekly expiry: on Tuesday, this week's Thursday is only 2 days away
        # (high theta risk) → skip it and use NEXT week's Thursday instead.
        # Jump past this week's Thursday by adding 3 days (lands on Friday),
        # then find the next Thursday from there.
        next_thu = get_next_thursday(d + timedelta(days=3))
        logger.info(f"Tuesday rule: using next weekly expiry {next_thu}")
        return next_thu
    else:
        # Same-day expiry: find the Thursday of the current week
        # If today is Thursday → expiry is today
        # If today is Mon/Wed/Fri → find current week's Thursday
        current_week_thu = get_next_thursday(d)
        logger.debug(f"Using same-day/current-week expiry: {current_week_thu}")
        return current_week_thu


def format_expiry_for_symbol(expiry: date) -> str:
    """
    Convert expiry date to Kite symbol format.
    Example: date(2024, 6, 27) → "27JUN24"
    """
    return expiry.strftime("%d%b%y").upper()


def seconds_until_squareoff(current_time: datetime | None = None) -> int:
    """Returns seconds remaining until 11:30 AM squareoff. Negative if past."""
    t = current_time or now_ist()
    if t.tzinfo is None:
        t = IST.localize(t)
    squareoff_time = t.replace(hour=SQUAREOFF_HOUR, minute=SQUAREOFF_MINUTE, second=0, microsecond=0)
    delta = squareoff_time - t
    return int(delta.total_seconds())
