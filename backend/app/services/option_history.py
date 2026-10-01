"""
Option history
──────────────
Records real 1-minute option prices from Kite so backtests can replay the
premiums the engine would actually have traded, instead of a model.

Kite only lists (and serves history for) contracts that have not yet expired, so
capture has to happen while the contract is alive:
  - capture_day() runs every weekday after the close (see main.py), and
  - backfill_range() can be run by hand for recent past days whose weekly
    contract is still listed (a day's contract expires within the next 7 days).

For a day it stores every strike the engine's ATM-50 / ATM+50 rule could have
picked given that day's NIFTY range, for both sides.
"""
import time as _time
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.option_selector import build_option_symbol, get_option_strike
from app.core.time_rules import get_expiry_date
from app.db.database import SessionLocal
from app.models.models import OptionMinutePrices
from app.services.minute_series import NIFTY_SPOT_TOKEN, fetch_kite_minute_closes

# Kite allows ~3 historical-data requests a second
REQUEST_GAP_SECONDS = 0.4
MAX_SYMBOLS_PER_DAY = 30
MAX_BACKFILL_DAYS = 7


def candidate_contracts(nifty_closes: List[float], trade_date: date) -> List[dict]:
    """
    Every (side, strike) the engine's strike rule could select at any point in the
    day, given the day's NIFTY range, with the contract's symbol and expiry.
    """
    expiry = get_expiry_date(trade_date)
    contracts: Dict[str, dict] = {}
    low_atm = get_option_strike("PE", Decimal(str(min(nifty_closes)))) - 50   # ATM at the day's low
    high_atm = get_option_strike("PE", Decimal(str(max(nifty_closes)))) - 50  # ATM at the day's high
    for atm in range(low_atm, high_atm + 1, 50):
        for side in ("PE", "CE"):
            strike = atm + 50 if side == "PE" else atm - 50
            symbol = build_option_symbol(side, strike, expiry)
            contracts[symbol] = {"symbol": symbol, "side": side, "strike": strike, "expiry": expiry}
    return list(contracts.values())[:MAX_SYMBOLS_PER_DAY]


def capture_day(
    kite_service,
    trade_date: date,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    request_gap: float = REQUEST_GAP_SECONDS,
    force: bool = False,
) -> dict:
    """
    Fetch and store the day's candidate option series. Blocking (Kite calls plus
    a pause between them) - run it in an executor from async code.

    Returns {"date", "status", "saved", "skipped", "missing"} where status is
    "ok", "no_nifty_data" (nothing recorded - options are never captured against
    unknown spot), or "error".
    """
    result = {"date": trade_date.isoformat(), "status": "ok", "saved": 0, "skipped": 0, "missing": []}
    try:
        nifty = fetch_kite_minute_closes(kite_service, NIFTY_SPOT_TOKEN, trade_date, backfill_leading=True)
    except Exception as e:
        logger.warning(f"Option history {trade_date}: NIFTY history failed: {e}")
        result["status"] = "error"
        return result
    nifty_closes = [c for c in nifty if c is not None]
    if not nifty_closes:
        result["status"] = "no_nifty_data"
        return result

    with session_factory() as db:
        already = {
            row.symbol for row in
            db.query(OptionMinutePrices.symbol).filter(OptionMinutePrices.trade_date == trade_date)
        }
        for contract in candidate_contracts(nifty_closes, trade_date):
            symbol = contract["symbol"]
            if symbol in already and not force:
                result["skipped"] += 1
                continue
            token = kite_service.get_instrument_token(symbol)
            if token is None:  # contract already delisted (or symbol not in today's list)
                result["missing"].append(symbol)
                continue
            try:
                _time.sleep(request_gap)
                closes = fetch_kite_minute_closes(kite_service, token, trade_date)
            except Exception as e:
                logger.warning(f"Option history {trade_date} {symbol}: {e}")
                result["missing"].append(symbol)
                continue
            if not any(c is not None for c in closes):
                result["missing"].append(symbol)
                continue

            row = db.query(OptionMinutePrices).filter_by(trade_date=trade_date, symbol=symbol).first()
            if row is None:
                db.add(OptionMinutePrices(
                    trade_date=trade_date, symbol=symbol, side=contract["side"],
                    strike=contract["strike"], expiry=contract["expiry"], closes=closes,
                ))
            else:
                row.closes = closes
            db.commit()
            result["saved"] += 1

    logger.info(
        f"Option history {trade_date}: saved {result['saved']}, "
        f"already had {result['skipped']}, missing {len(result['missing'])}"
    )
    return result


def weekdays_between(start: date, end: date) -> List[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def backfill_range(kite_service, start: date, end: date, **kwargs) -> List[dict]:
    """capture_day() for each weekday in the range (blocking, sequential)."""
    return [capture_day(kite_service, d, **kwargs) for d in weekdays_between(start, end)]


def load_option_prices(db: Session, trade_date: date) -> Dict[str, List[Optional[float]]]:
    """symbol -> 375-slot minute closes for every recorded contract on the day."""
    rows = db.query(OptionMinutePrices).filter(OptionMinutePrices.trade_date == trade_date).all()
    return {row.symbol: list(row.closes) for row in rows}


def recorded_symbol_counts(db: Session, start: date, end: date) -> Dict[date, int]:
    """How many contracts are recorded for each day in the range."""
    counts: Dict[date, int] = {}
    rows = (
        db.query(OptionMinutePrices.trade_date)
        .filter(OptionMinutePrices.trade_date >= start, OptionMinutePrices.trade_date <= end)
        .all()
    )
    for (d,) in rows:
        counts[d] = counts.get(d, 0) + 1
    return counts
