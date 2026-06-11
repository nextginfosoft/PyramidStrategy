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
