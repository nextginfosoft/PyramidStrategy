"""
Option premium model
────────────────────
Black-Scholes price for a NIFTY option, used by the backtest on days where no
recorded option prices exist. It prices the strike/expiry the engine would
actually have bought, so the entry premium, the time decay and the option's
sensitivity to NIFTY are all realistic in shape - but the volatility is one
assumed number for the whole day, so treat the result as an estimate.
"""
import math
from datetime import date, datetime, time, timedelta

from app.services.minute_series import MARKET_OPEN_MINUTES

RISK_FREE_RATE = 0.065
DEFAULT_IV = 0.14
EXPIRY_CLOSE = time(15, 30)
TICK = 0.05


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(side: str, spot: float, strike: float, t_years: float, iv: float,
             r: float = RISK_FREE_RATE) -> float:
    """European Black-Scholes price. Falls back to intrinsic value at/after expiry."""
    intrinsic = max(0.0, spot - strike) if side == "CE" else max(0.0, strike - spot)
    if t_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return intrinsic
    vol_sqrt_t = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    discounted_strike = strike * math.exp(-r * t_years)
    if side == "CE":
        return spot * _norm_cdf(d1) - discounted_strike * _norm_cdf(d2)
    return discounted_strike * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def years_to_expiry(expiry: date, trade_date: date, minute_idx: int) -> float:
    """Calendar time from the given bar (minute_idx 0 = 9:15) to expiry at 15:30."""
    now = datetime.combine(trade_date, time(0, 0)) + timedelta(minutes=MARKET_OPEN_MINUTES + minute_idx)
    expires = datetime.combine(expiry, EXPIRY_CLOSE)
    return max(0.0, (expires - now).total_seconds() / (365.0 * 86400.0))


def model_premium(side: str, spot: float, strike: int, expiry: date, trade_date: date,
                  minute_idx: int, iv: float = DEFAULT_IV) -> float:
    """Modelled premium at a bar, rounded to the exchange tick (never below one tick)."""
    price = bs_price(side, spot, strike, years_to_expiry(expiry, trade_date, minute_idx), iv)
    return max(TICK, round(round(price / TICK) * TICK, 2))
