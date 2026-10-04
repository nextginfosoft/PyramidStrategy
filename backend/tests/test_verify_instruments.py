"""scripts/verify_instruments.py comparison logic, against fake dumps (no network)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_instruments import compare  # noqa: E402

from app.core.instruments import get_instrument  # noqa: E402

TODAY = date(2026, 10, 5)


def opt(name, expiry, strike, lot):
    return {"name": name, "segment": "NFO-OPT", "expiry": expiry, "strike": strike, "lot_size": lot}


def banknifty_dump(lot=30):
    return [opt("BANKNIFTY", e, k, lot) for e in (date(2026, 10, 27), date(2026, 11, 23), date(2026, 12, 29))
            for k in (54900, 55000, 55100)]


NSE = [{"tradingsymbol": "NIFTY BANK", "instrument_token": 260105},
       {"tradingsymbol": "NIFTY 50", "instrument_token": 256265}]


def test_matching_dump_has_no_problems():
    assert compare(banknifty_dump(), NSE, get_instrument("BANKNIFTY"), TODAY) == []


def test_lot_size_mismatch_reported():
    problems = compare(banknifty_dump(lot=15), NSE, get_instrument("BANKNIFTY"), TODAY)
    assert any("lot size" in p for p in problems)


def test_unlisted_predicted_expiry_reported():
    dump = [opt("BANKNIFTY", date(2026, 10, 28), k, 30) for k in (54900, 55000, 55100)]
    assert any("not listed" in p for p in compare(dump, NSE, get_instrument("BANKNIFTY"), TODAY))


def test_wrong_spot_token_reported():
    bad = [{"tradingsymbol": "NIFTY BANK", "instrument_token": 1}]
    assert any("spot token" in p for p in compare(banknifty_dump(), bad, get_instrument("BANKNIFTY"), TODAY))


def test_missing_instrument_reported():
    assert any("no NFO options" in p for p in compare([], NSE, get_instrument("BANKNIFTY"), TODAY))
