"""
Instrument registry
───────────────────
Per-instrument constants (spot token, strike step, lot size, expiry style, ...)
so the strategy code is not hardcoded to NIFTY. NIFTY stays the default
everywhere, so existing behaviour is unchanged.

NOTE: BANKNIFTY lot size and expiry rules are exchange-controlled and change
over time. The values below are defaults; verify against the live Kite
instruments dump (`kite.instruments("NFO")` → `lot_size`, `expiry`) before any
live use. BANKNIFTY is paper-trade only.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

DEFAULT_INSTRUMENT = "NIFTY"

WEEKLY_TUESDAY = "WEEKLY_TUESDAY"
MONTHLY_LAST_TUESDAY = "MONTHLY_LAST_TUESDAY"


@dataclass(frozen=True)
class InstrumentSpec:
    name: str                  # also the option symbol prefix and Kite "name"
    spot_symbol: str           # Kite REST key for the spot index, e.g. "NSE:NIFTY 50"
    spot_token: int            # Kite instrument token of the spot index
    strike_step: int           # distance between listed strikes
    option_offset: int         # PE: ATM + offset, CE: ATM - offset
    lot_size: int
    expiry_rule: str           # WEEKLY_TUESDAY | MONTHLY_LAST_TUESDAY
    est_time_value_peak: Decimal   # paper-trade price estimator: ATM time value
    est_time_value_decay: Decimal  # time value lost per index point from ATM
    est_fallback_spot: Decimal     # placeholder spot when no tick received yet
    paper_only: bool = False

    @property
    def ltp_cache_key(self) -> str:
        """Redis key holding the latest spot tick ('nifty:ltp' kept for NIFTY)."""
        return "nifty:ltp" if self.name == DEFAULT_INSTRUMENT else f"{self.name.lower()}:ltp"


INSTRUMENTS: dict[str, InstrumentSpec] = {
    "NIFTY": InstrumentSpec(
        name="NIFTY",
        spot_symbol="NSE:NIFTY 50",
        spot_token=256265,
        strike_step=50,
        option_offset=50,
        lot_size=65,  # NSE revised lot (was 75); verify against Kite instruments dump
        expiry_rule=WEEKLY_TUESDAY,
        est_time_value_peak=Decimal("80"),
        est_time_value_decay=Decimal("0.5"),
        est_fallback_spot=Decimal("23200"),
    ),
    "BANKNIFTY": InstrumentSpec(
        name="BANKNIFTY",
        spot_symbol="NSE:NIFTY BANK",
        spot_token=260105,
        strike_step=100,
        option_offset=100,
        lot_size=30,  # verify against Kite instruments dump
        expiry_rule=MONTHLY_LAST_TUESDAY,  # weekly BANKNIFTY contracts no longer listed
        est_time_value_peak=Decimal("200"),
        est_time_value_decay=Decimal("0.4"),
        est_fallback_spot=Decimal("52000"),
        paper_only=True,
    ),
}


def get_instrument(name: Optional[str] = None) -> InstrumentSpec:
    """Look up an instrument by name (case-insensitive). None → NIFTY."""
    key = (name or DEFAULT_INSTRUMENT).upper()
    try:
        return INSTRUMENTS[key]
    except KeyError:
        raise ValueError(f"Unsupported instrument: {name}. Supported: {', '.join(INSTRUMENTS)}")


def instrument_from_symbol(symbol: str) -> InstrumentSpec:
    """Infer the instrument from an option symbol such as 'BANKNIFTY26OCT55000CE'."""
    for name in sorted(INSTRUMENTS, key=len, reverse=True):
        if symbol.startswith(name):
            return INSTRUMENTS[name]
    return INSTRUMENTS[DEFAULT_INSTRUMENT]
