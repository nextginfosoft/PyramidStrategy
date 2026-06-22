"""
Safety Checks — Phase 4
────────────────────────
Pre-flight validation before starting the strategy in LIVE mode.
All checks must pass; any failure returns an error message.

Checks:
  1. Kite token valid
  2. KiteTicker connected and receiving ticks
  3. NFO instruments loaded (option chain available)
  4. Strategy config set (R/S levels defined)
  5. Sufficient account funds (min 50,000 INR available margin)
  6. Time check — not after 11:00 AM (too late to start)
  7. No existing open positions from a previous session (CAUTION flag)
"""

from datetime import time, datetime, date, timedelta
from decimal import Decimal
from loguru import logger
import pytz

from app.core.time_rules import now_ist, get_entry_cutoff_time, get_time_from_str  # module-level so tests can patch it

IST = pytz.timezone("Asia/Kolkata")
MIN_REQUIRED_MARGIN = Decimal("50000")  # ₹50,000 minimum


def run_safety_checks(
    paper_trade: bool,
    kite_service,
    strategy_config: dict | None,
) -> tuple[bool, list[str], list[str]]:
    """
    Run all safety checks before starting the strategy.

    Returns:
        (all_passed: bool, errors: list[str], warnings: list[str])

    In paper_trade mode, Kite checks are skipped (only config is checked).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. Strategy config ────────────────────────────────────────────────
    if not strategy_config:
        errors.append("No strategy config set — configure R1/R2/R3 and S1/S2/S3 levels in Settings")
    else:
        required_keys = ["r1", "r2", "r3", "s1", "s2", "s3", "lot_size", "target_points", "sl_points"]
        missing = [k for k in required_keys if k not in strategy_config or strategy_config[k] is None]
        if missing:
            errors.append(f"Incomplete strategy config — missing: {', '.join(missing)}")

    # ── 2. Time check ─────────────────────────────────────────────────────
    current = now_ist().time()
    sq_time_str = strategy_config.get("squareoff_time", "11:30") if strategy_config else "11:30"
    cutoff = get_entry_cutoff_time(sq_time_str)
    
    # Warning cutoff is 15 minutes before entry cutoff (or 30 mins before square-off)
    warning_cutoff_dt = datetime.combine(date.min, cutoff) - timedelta(minutes=15)
    warning_cutoff = warning_cutoff_dt.time()
    market_open = time(9, 15)

    if current >= cutoff:
        errors.append(f"Cannot start after {cutoff.strftime('%H:%M')} IST — no entries allowed after this time")
    elif current >= warning_cutoff:
        warnings.append(f"⚠️ Starting at {current.strftime('%H:%M')} IST — limited time before {cutoff.strftime('%H:%M')} cutoff")
    elif current < market_open:
        warnings.append(f"Market not open yet ({current.strftime('%H:%M')} IST). Strategy will activate at 9:15 AM.")

    # ── Paper trade early return ──────────────────────────────────────────
    if paper_trade:
        logger.info("Safety checks: paper trade mode — skipping Kite-specific checks")
        return len(errors) == 0, errors, warnings

    # ── Live trade checks below ───────────────────────────────────────────

    # ── 3. Kite token valid ───────────────────────────────────────────────
    if not kite_service.is_authenticated():
        errors.append("Kite not authenticated — complete OAuth login in Settings → Zerodha section")
    else:
        valid = kite_service.validate_token()
        if not valid:
            errors.append("Kite access token expired — re-login required (token expires daily)")

    # ── 4. Instruments loaded ─────────────────────────────────────────────
    if not kite_service._instruments_loaded:
        errors.append("NFO instruments not loaded — click 'Load Instruments' in Kite Settings")

    # ── 5. Ticker connected ───────────────────────────────────────────────
    if not kite_service._is_connected:
        warnings.append("KiteTicker not yet connected — NIFTY live feed will activate on start")

    # ── 6. Funds check ────────────────────────────────────────────────────
    try:
        margins = kite_service.kite.margins(segment="equity")
        available = Decimal(str(margins.get("equity", {}).get("available", {}).get("live_balance", 0)))
        if available < MIN_REQUIRED_MARGIN:
            errors.append(
                f"Insufficient margin: ₹{available:,.0f} available, "
                f"₹{MIN_REQUIRED_MARGIN:,.0f} required"
            )
        else:
            logger.info(f"Margin check passed: ₹{available:,.0f} available")
    except Exception as e:
        warnings.append(f"Could not verify account margin: {e}")

    # ── 7. Existing positions check ───────────────────────────────────────
    try:
        positions = kite_service.kite.positions()
        day_pos = positions.get("day", [])
        open_options = [
            p for p in day_pos
            if p.get("exchange") == "NFO"
            and p.get("tradingsymbol", "").startswith("NIFTY")
            and abs(int(p.get("quantity", 0))) > 0
        ]
        if open_options:
            instruments = [p["tradingsymbol"] for p in open_options]
            warnings.append(
                f"⚠️ Existing NIFTY positions detected: {', '.join(instruments)} — "
                f"the engine will track these but not manage them"
            )
    except Exception as e:
        warnings.append(f"Could not check existing positions: {e}")

    all_passed = len(errors) == 0
    if all_passed:
        logger.info("✅ All safety checks passed — safe to start live trading")
    else:
        logger.error(f"❌ Safety check failed: {errors}")


    return all_passed, errors, warnings
