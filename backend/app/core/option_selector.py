"""
Option Selector
───────────────
Finds the correct ATM±50 option symbol for a given NIFTY price and side.

Rules from CLAUDE.md:
  PE: ATM + 50 strike (same-day expiry, except Tuesday)
  CE: ATM - 50 strike (same-day expiry, except Tuesday)
  Strike at L1 is LOCKED — this module is called only at Level 1 entry.
"""

from decimal import Decimal
from datetime import date
from loguru import logger
from app.core.time_rules import get_expiry_date, format_expiry_for_symbol


def get_atm_strike(nifty_ltp: Decimal) -> int:
    """
    Round NIFTY price to the nearest 50 to get ATM strike.
    e.g. 23,186 → 23,200  |  23,162 → 23,150
    """
    price = float(nifty_ltp)
    return int(round(price / 50) * 50)


def get_option_strike(side: str, nifty_ltp: Decimal) -> int:
    """
    PE: ATM + 50 (buy slightly OTM put when NIFTY hits resistance)
    CE: ATM - 50 (buy slightly OTM call when NIFTY hits support)
    """
    atm = get_atm_strike(nifty_ltp)
    if side == "PE":
        strike = atm + 50
    elif side == "CE":
        strike = atm - 50
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'CE' or 'PE'")
    logger.debug(f"[{side}] NIFTY={nifty_ltp} | ATM={atm} | Selected strike={strike}")
    return strike


def build_option_symbol(side: str, strike: int, expiry: date) -> str:
    """
    Build Kite-compatible option symbol.
    Format: NIFTY{DDMMMYY}{STRIKE}{CE/PE}
    Example: NIFTY27JUN2423150PE
    """
    expiry_str = format_expiry_for_symbol(expiry)
    symbol = f"NIFTY{expiry_str}{strike}{side}"
    logger.debug(f"Built symbol: {symbol}")
    return symbol


def get_option_details(side: str, nifty_ltp: Decimal, trade_date: date | None = None) -> dict:
    """
    Main entry point: given NIFTY price and side, return full option details.

    Returns:
        {
            "symbol": "NIFTY27JUN2423150PE",
            "strike": 23150,
            "expiry": date(2024, 6, 27),
            "side": "PE"
        }
    """
    expiry = get_expiry_date(trade_date)
    strike = get_option_strike(side, nifty_ltp)
    symbol = build_option_symbol(side, strike, expiry)

    logger.info(
        f"[{side}] Option selected: {symbol} | strike={strike} | expiry={expiry} "
        f"| NIFTY={nifty_ltp:.2f}"
    )

    return {
        "symbol": symbol,
        "strike": strike,
        "expiry": expiry,
        "side": side,
    }


def estimate_option_price(symbol: str, nifty_ltp: Decimal) -> Decimal:
    """
    Dynamically estimate option price based on NIFTY LTP and strike.
    Uses intrinsic value + decaying time value (80 pts peak at ATM).
    """
    try:
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

        # Calculate time value: peak of 80 points at ATM, decaying by 0.5 per point OTM/ITM
        dist = abs(nifty_ltp - Decimal(strike))
        time_val = max(Decimal("5.00"), Decimal("80.00") - dist * Decimal("0.5"))

        price = intrinsic + time_val
        return max(Decimal("0.05"), price.quantize(Decimal("0.01")))
    except Exception as e:
        logger.warning(f"Error estimating option price for {symbol}: {e}")
        return Decimal("100.00")
