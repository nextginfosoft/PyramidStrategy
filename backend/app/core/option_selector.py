"""
Option Selector
───────────────
Finds the correct ATM±offset option symbol for a given index price and side.

Rules from CLAUDE.md (NIFTY: offset 50; BANKNIFTY: offset 100, see instruments.py):
  PE: ATM + offset (same-day expiry, except Tuesday)
  CE: ATM - offset (same-day expiry, except Tuesday)
  Strike at L1 is LOCKED — this module is called only at Level 1 entry.

All functions take an optional `instrument` (name or InstrumentSpec); the
default is NIFTY, so existing callers behave exactly as before.
"""

from decimal import Decimal
from datetime import date
from loguru import logger
from app.core.time_rules import get_expiry_date, get_monthly_expiry_date, format_expiry_for_symbol
from app.core.instruments import (
    InstrumentSpec, MONTHLY_LAST_TUESDAY, get_instrument, instrument_from_symbol,
)


def _spec(instrument: str | InstrumentSpec | None) -> InstrumentSpec:
    return instrument if isinstance(instrument, InstrumentSpec) else get_instrument(instrument)


def get_instrument_expiry(instrument: str | InstrumentSpec | None = None,
                          trade_date: date | None = None) -> date:
    """Expiry for the instrument's contract style (weekly vs monthly-only)."""
    spec = _spec(instrument)
    if spec.expiry_rule == MONTHLY_LAST_TUESDAY:
        return get_monthly_expiry_date(trade_date)
    return get_expiry_date(trade_date)


def get_atm_strike(nifty_ltp: Decimal, instrument: str | InstrumentSpec | None = None) -> int:
    """
    Round the index price to the nearest strike step to get ATM strike.
    NIFTY (step 50): 23,186 → 23,200  |  23,162 → 23,150
    """
    step = _spec(instrument).strike_step
    price = float(nifty_ltp)
    return int(round(price / step) * step)


def get_option_strike(side: str, nifty_ltp: Decimal, instrument: str | InstrumentSpec | None = None) -> int:
    """
    PE: ATM + offset (buy slightly OTM put when the index hits resistance)
    CE: ATM - offset (buy slightly OTM call when the index hits support)
    """
    spec = _spec(instrument)
    atm = get_atm_strike(nifty_ltp, spec)
    if side == "PE":
        strike = atm + spec.option_offset
    elif side == "CE":
        strike = atm - spec.option_offset
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'CE' or 'PE'")
    logger.debug(f"[{side}] {spec.name}={nifty_ltp} | ATM={atm} | Selected strike={strike}")
    return strike


def build_option_symbol(side: str, strike: int, expiry: date,
                        instrument: str | InstrumentSpec | None = None) -> str:
    """
    Build Kite-compatible option symbol.
    Format: {NAME}{expiry}{STRIKE}{CE/PE}
    Examples: NIFTY27JUN2423150PE, BANKNIFTY26OCT55000CE
    """
    spec = _spec(instrument)
    monthly = True if spec.expiry_rule == MONTHLY_LAST_TUESDAY else None
    expiry_str = format_expiry_for_symbol(expiry, monthly=monthly)
    symbol = f"{spec.name}{expiry_str}{strike}{side}"
    logger.debug(f"Built symbol: {symbol}")
    return symbol


def get_option_details(side: str, nifty_ltp: Decimal, trade_date: date | None = None,
                       instrument: str | InstrumentSpec | None = None) -> dict:
    """
    Main entry point: given index price and side, return full option details.

    Returns:
        {
            "symbol": "NIFTY27JUN2423150PE",
            "strike": 23150,
            "expiry": date(2024, 6, 27),
            "side": "PE"
        }
    """
    spec = _spec(instrument)
    expiry = get_instrument_expiry(spec, trade_date)
    strike = get_option_strike(side, nifty_ltp, spec)
    symbol = build_option_symbol(side, strike, expiry, spec)

    logger.info(
        f"[{side}] Option selected: {symbol} | strike={strike} | expiry={expiry} "
        f"| {spec.name}={nifty_ltp:.2f}"
    )

    return {
        "symbol": symbol,
        "strike": strike,
        "expiry": expiry,
        "side": side,
    }


def estimate_option_price(symbol: str, nifty_ltp: Decimal,
                          instrument: str | InstrumentSpec | None = None) -> Decimal:
    """
    Dynamically estimate option price based on index LTP and strike.
    Uses intrinsic value + decaying time value (peak at ATM; NIFTY 80 pts).
    Instrument is inferred from the symbol prefix when not given.
    """
    try:
        spec = _spec(instrument) if instrument else instrument_from_symbol(symbol)
        side = symbol[-2:]
        # Extract digits block before side
        digits = ""
        for char in reversed(symbol[:-2]):
            if char.isdigit():
                digits = char + digits
            else:
                break
        strike = int(digits[-5:]) if len(digits) > 5 else int(digits)

        # Calculate intrinsic value
        if side == "CE":
            intrinsic = max(Decimal("0"), nifty_ltp - Decimal(strike))
        else:
            intrinsic = max(Decimal("0"), Decimal(strike) - nifty_ltp)

        # Time value: peak at ATM, decaying per point OTM/ITM (constants per instrument)
        dist = abs(nifty_ltp - Decimal(strike))
        time_val = max(
            Decimal("5.00"),
            spec.est_time_value_peak - dist * spec.est_time_value_decay,
        )

        price = intrinsic + time_val
        return max(Decimal("0.05"), price.quantize(Decimal("0.01")))
    except Exception as e:
        logger.warning(f"Error estimating option price for {symbol}: {e}")
        return Decimal("100.00")
