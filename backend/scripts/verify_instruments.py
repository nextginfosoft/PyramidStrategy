"""
Check the instrument registry (app/core/instruments.py) against Zerodha's live
instrument dump: lot size, spot token, spot symbol and monthly/weekly expiry dates.

Read-only. Needs a valid Kite session — pass credentials via environment so they
never touch the repo:

    set KITE_API_KEY=...        (PowerShell: $env:KITE_API_KEY="...")
    set KITE_ACCESS_TOKEN=...
    python scripts/verify_instruments.py

Exit code 0 = registry matches the dump, 1 = mismatches (listed), 2 = could not run.
"""
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.instruments import INSTRUMENTS, MONTHLY_LAST_TUESDAY, InstrumentSpec  # noqa: E402
from app.core.option_selector import get_instrument_expiry  # noqa: E402


def compare(nfo: list[dict], nse: list[dict], spec: InstrumentSpec, today: date | None = None) -> list[str]:
    """Return human-readable mismatches between `spec` and the instrument dumps (empty = OK)."""
    today = today or date.today()
    problems: list[str] = []

    opts = [i for i in nfo if i.get("name") == spec.name and i.get("segment") == "NFO-OPT"]
    if not opts:
        return [f"{spec.name}: no NFO options found in the dump"]

    lots = {int(i["lot_size"]) for i in opts}
    if lots != {spec.lot_size}:
        problems.append(f"{spec.name}: lot size in dump {sorted(lots)} != registry {spec.lot_size}")

    steps = set()
    for exp in {i["expiry"] for i in opts}:
        strikes = sorted({float(i["strike"]) for i in opts if i["expiry"] == exp})
        steps |= {int(b - a) for a, b in zip(strikes, strikes[1:])}
    if spec.strike_step not in steps:
        problems.append(f"{spec.name}: strike step {spec.strike_step} not seen in dump (steps: {sorted(steps)[:6]})")

    expiries = sorted(e for e in {i["expiry"] for i in opts} if e >= today)
    if not expiries:
        problems.append(f"{spec.name}: no future expiries in the dump")
    else:
        # What the registry's expiry rule would pick today must be a real, listed expiry
        try:
            predicted = get_instrument_expiry(spec, today)
            if predicted not in expiries:
                problems.append(f"{spec.name}: rule predicts expiry {predicted}, not listed (next listed: {expiries[:4]})")
        except Exception as e:  # pragma: no cover - defensive
            problems.append(f"{spec.name}: expiry rule failed: {e}")
        if spec.expiry_rule == MONTHLY_LAST_TUESDAY:
            months = {(e.year, e.month) for e in expiries[:6]}
            if len(months) < min(len(expiries[:6]), 2) or len(expiries[:3]) != len({(e.year, e.month) for e in expiries[:3]}):
                problems.append(f"{spec.name}: registry says monthly-only but dump lists several expiries per month: {expiries[:6]}")

    sym = spec.spot_symbol.split(":", 1)[1]
    spot = [i for i in nse if i.get("tradingsymbol") == sym]
    if not spot:
        problems.append(f"{spec.name}: spot symbol {spec.spot_symbol!r} not found in NSE dump")
    elif int(spot[0]["instrument_token"]) != spec.spot_token:
        problems.append(f"{spec.name}: spot token in dump {spot[0]['instrument_token']} != registry {spec.spot_token}")
    return problems


def main() -> int:
    api_key, token = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
    if not api_key or not token:
        print("Set KITE_API_KEY and KITE_ACCESS_TOKEN in the environment first.")
        return 2
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(token)
    try:
        nfo, nse = kite.instruments("NFO"), kite.instruments("NSE")
    except Exception as e:
        print(f"Could not fetch instruments: {e}")
        return 2

    failed = False
    for spec in INSTRUMENTS.values():
        problems = compare(nfo, nse, spec)
        print(f"[{'FAIL' if problems else ' OK '}] {spec.name}")
        for p in problems:
            print(f"        - {p}")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
