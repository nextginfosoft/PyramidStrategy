"""
Minute series helpers
─────────────────────
Turn Kite 1-minute candles into a list indexed by minute since the 9:15 open,
so a NIFTY series and an option series for the same day line up bar for bar
even when some minutes have no candle (illiquid strikes often skip minutes).
"""
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from app.core.time_rules import IST

# NSE:NIFTY 50 spot index token
NIFTY_SPOT_TOKEN = 256265

# NSE session: 9:15 to 15:30, one bar per minute (09:15 ... 15:29)
MARKET_OPEN_MINUTES = 9 * 60 + 15
MINUTES_PER_DAY = 375


def align_minute_closes(
    records: List[Dict[str, Any]], *, backfill_leading: bool = False
) -> List[Optional[float]]:
    """
    Place each candle's close at its minute slot (0 = the 9:15 bar).

    Gaps between two candles carry the previous close forward (the price did not
    change if nothing traded). Slots after the last candle stay None, so a
    half-finished day is not padded with invented flat prices. Slots before the
    first candle stay None unless `backfill_leading` (used for the NIFTY index,
    which always ticks).
    """
    closes: List[Optional[float]] = [None] * MINUTES_PER_DAY
    last_idx = -1
    for r in records:
        dt = r["date"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is not None:
            dt = dt.astimezone(IST)
        idx = dt.hour * 60 + dt.minute - MARKET_OPEN_MINUTES
        if 0 <= idx < MINUTES_PER_DAY:
            closes[idx] = float(r["close"])
            last_idx = max(last_idx, idx)

    last: Optional[float] = None
    for i in range(last_idx + 1):
        if closes[i] is None:
            closes[i] = last
        else:
            last = closes[i]

    if backfill_leading:
        first = next((c for c in closes if c is not None), None)
        if first is not None:
            for i in range(MINUTES_PER_DAY):
                if closes[i] is not None:
                    break
                closes[i] = first
    return closes


def fetch_kite_minute_closes(
    kite_service, instrument_token: int, day: date, *, backfill_leading: bool = False
) -> List[Optional[float]]:
    """Blocking Kite call: one day of 1-minute closes for any instrument token."""
    records = kite_service._kite.historical_data(
        instrument_token=instrument_token,
        from_date=datetime.combine(day, time.min),
        to_date=datetime.combine(day, time.max),
        interval="minute",
    )
    return align_minute_closes(records or [], backfill_leading=backfill_leading)


def trim_to_data(closes: List[Optional[float]]) -> List[float]:
    """The prefix of a series that has data (drops the un-filled tail)."""
    last = max((i for i, c in enumerate(closes) if c is not None), default=-1)
    return [float(c) for c in closes[: last + 1] if c is not None]
