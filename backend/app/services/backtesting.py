import asyncio
import hashlib
import random
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import StrategyConfig, Trade
from app.core.option_selector import build_option_symbol, get_option_strike
from app.core.state_machine import StateMachine, State
from app.core.time_rules import get_expiry_date
from app.services.minute_series import NIFTY_SPOT_TOKEN, fetch_kite_minute_closes, trim_to_data
from app.services.option_history import load_option_prices
from app.services.option_pricing import DEFAULT_IV, model_premium


def _no_entry_minutes(no_entry_time: Optional[str], sq_minutes: int) -> Optional[int]:
    """Minutes-since-midnight of a user-configured no-entry time (capped at square-off), or None if unset/invalid."""
    if not no_entry_time:
        return None
    try:
        h, m = map(int, str(no_entry_time).split(":"))
    except Exception:
        return None
    return min(h * 60 + m, sq_minutes)


def get_nifty_data_for_day(date_str: str) -> List[float]:
    """
    Generate realistic, deterministic NIFTY spot prices for a given date.
    Seed is based on the date, so running it multiple times produces identical results.
    """
    seed_str = f"nifty_seed_{date_str}"
    seed_val = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest(), 16) % 10000000
    random.seed(seed_val)

    # Base price of NIFTY around 23500-24500
    base_price = 24000.0 + random.uniform(-300, 300)
    prices = []
    current_price = base_price
    
    # 375 minutes (9:15 AM to 3:30 PM)
    for _ in range(375):
        # random walk with slight mean reversion to keep it bounded
        change = random.uniform(-4.0, 4.0)
        current_price += change
        prices.append(round(current_price, 2))
        
    return prices

async def fetch_historical_nifty(
    kite_service,
    start_date: date,
    end_date: date,
    sources: Optional[Dict[str, str]] = None,
) -> Dict[str, List[float]]:
    """
    Fetch historical Nifty spot index prices per day (one close per minute from 9:15).
    Falls back to simulated random-walk data - per day - if Kite is not
    authenticated or returns nothing. If `sources` is given it is filled with
    {date: "REAL" | "MOCK"} so callers can tell which days are simulated.
    """
    data = {}
    current_date = start_date
    delta = timedelta(days=1)

    # Try fetching via Kite if available
    kite_available = False
    if kite_service and kite_service.is_authenticated():
        try:
            # Test api call
            kite_service.validate_token()
            kite_available = True
        except Exception:
            pass

    loop = asyncio.get_running_loop()
    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            current_date += delta
            continue

        date_str = current_date.strftime("%Y-%m-%d")
        day_prices: List[float] = []

        if kite_available:
            try:
                closes = await loop.run_in_executor(
                    None,
                    lambda d=current_date: fetch_kite_minute_closes(
                        kite_service, NIFTY_SPOT_TOKEN, d, backfill_leading=True
                    ),
                )
                day_prices = trim_to_data(closes)
            except Exception as e:
                logger.warning(f"Error fetching historical data for {date_str}: {e}")
                day_prices = []

        # Fallback to mock data if Kite failed or returned empty
        source = "REAL"
        if not day_prices:
            day_prices = get_nifty_data_for_day(date_str)
            source = "MOCK"

        data[date_str] = day_prices
        if sources is not None:
            sources[date_str] = source
        current_date += delta

    return data

def run_single_backtest(
    date_str: str,
    nifty_prices: List[float],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Replay a single day's prices through the state machines.
    Returns list of trades completed during the day.
    """
    if not nifty_prices:
        return []
        
    r1, r2, r3 = Decimal(str(config["r1"])), Decimal(str(config["r2"])), Decimal(str(config["r3"]))
    s1, s2, s3 = Decimal(str(config["s1"])), Decimal(str(config["s2"])), Decimal(str(config["s3"]))
    target_pts = Decimal(str(config["target_points"]))
    sl_pts = Decimal(str(config["sl_points"]))
    lot_size = config.get("lot_size", 75)
    
    # Initialize separate StateMachines for PE and CE
    ce_sm = StateMachine(side="CE", lot_size=lot_size, target_points=target_pts, sl_points=sl_pts)
    pe_sm = StateMachine(side="PE", lot_size=lot_size, target_points=target_pts, sl_points=sl_pts)
    
    # Track the Nifty price at entry level to calculate option price changes
    # CE options gain when Nifty goes up: opt_price = 100 + 0.5 * (nifty - nifty_entry_l1)
    # PE options gain when Nifty goes down: opt_price = 100 + 0.5 * (nifty_entry_l1 - nifty)
    l1_entry_nifty = {"CE": None, "PE": None}
    
    trades = []
    
    # Helper to calculate simulated option LTP
    def get_opt_ltp(side: str, current_nifty: Decimal) -> Decimal:
        entry_n = l1_entry_nifty[side]
        if entry_n is None:
            return Decimal("100.0")
        diff = current_nifty - entry_n
        if side == "CE":
            return Decimal("100.0") + Decimal("0.5") * diff
        else:
            return Decimal("100.0") - Decimal("0.5") * diff

    prev_nifty = None
    
    # Replay minute-by-minute
    sq_time_str = config.get("squareoff_time", "11:30")
    sq_h, sq_m = map(int, sq_time_str.split(":"))
    sq_minutes = sq_h * 60 + sq_m
    explicit_cutoff = _no_entry_minutes(config.get("no_entry_time"), sq_minutes)
    cutoff_minutes = explicit_cutoff if explicit_cutoff is not None else sq_minutes - 15

    for minute_idx, price in enumerate(nifty_prices):
        nifty_ltp = Decimal(str(price))
        time_val = 915 + (minute_idx // 60) * 100 + (minute_idx % 60)
        
        # Format a pseudo-timestamp
        hour = 9 + (minute_idx + 15) // 60
        minute = (minute_idx + 15) % 60
        time_str = f"{hour:02d}:{minute:02d}:00"
        current_minutes = hour * 60 + minute
        
        # Force Squareoff
        if current_minutes >= sq_minutes:
            for sm in (ce_sm, pe_sm):
                if sm.state not in (State.IDLE, State.BLOCKED):
                    opt_price = get_opt_ltp(sm.side, nifty_ltp)
                    # Force exit
                    exit_res = sm.exit_position(opt_price, "SQUAREOFF")
                    trades.append({
                        "date": date_str,
                        "side": sm.side,
                        "level": sm.mapped_level(exit_res["level_blocked"]),
                        "lots": exit_res["lots"],
                        "qty": exit_res["qty"],
                        "entry_time": getattr(sm, "_entry_time_str", "09:15:00"),
                        "entry_price": float(exit_res["entry_avg_price"]),
                        "exit_time": time_str,
                        "exit_price": float(exit_res["exit_price"]),
                        "exit_reason": "SQUAREOFF",
                        "pnl": float(exit_res["pnl_rupees"])
                    })
                    l1_entry_nifty[sm.side] = None
            continue
            
        # Standard Processing
        for sm in (ce_sm, pe_sm):
            side = sm.side
            
            # Check target/SL
            if sm.state not in (State.IDLE, State.BLOCKED):
                opt_price = get_opt_ltp(side, nifty_ltp)
                
                if sm.check_target(opt_price):
                    exit_res = sm.exit_position(opt_price, "TARGET")
                    trades.append({
                        "date": date_str,
                        "side": side,
                        "level": sm.mapped_level(exit_res["level_blocked"]),
                        "lots": exit_res["lots"],
                        "qty": exit_res["qty"],
                        "entry_time": getattr(sm, "_entry_time_str", "09:15:00"),
                        "entry_price": float(exit_res["entry_avg_price"]),
                        "exit_time": time_str,
                        "exit_price": float(exit_res["exit_price"]),
                        "exit_reason": "TARGET",
                        "pnl": float(exit_res["pnl_rupees"])
                    })
                    l1_entry_nifty[side] = None
                    
                elif sm.check_sl(opt_price):
                    exit_res = sm.exit_position(opt_price, "SL")
                    trades.append({
                        "date": date_str,
                        "side": side,
                        "level": sm.mapped_level(exit_res["level_blocked"]),
                        "lots": exit_res["lots"],
                        "qty": exit_res["qty"],
                        "entry_time": getattr(sm, "_entry_time_str", "09:15:00"),
                        "entry_price": float(exit_res["entry_avg_price"]),
                        "exit_time": time_str,
                        "exit_price": float(exit_res["exit_price"]),
                        "exit_reason": "SL",
                        "pnl": float(exit_res["pnl_rupees"])
                    })
                    l1_entry_nifty[side] = None
                    
            # Check new entries
            if current_minutes < cutoff_minutes and sm.state in (State.IDLE, State.L1_ENTERED, State.L2_ENTERED):
                # We need a 1-minute cooldown between entries
                cooldown_elapsed = getattr(sm, "_last_entry_minute", -10) != minute_idx - 1
                
                if side == "PE":
                    if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty < r1 and nifty_ltp >= r1:
                        l1_entry_nifty[side] = nifty_ltp
                        sm.enter_level1("NIFTY_MOCK_PE", int(r1), date_str, Decimal("100.0"))
                        sm._entry_time_str = time_str
                        sm._last_entry_minute = minute_idx
                    elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r2 and nifty_ltp >= r2:
                        opt_price = get_opt_ltp(side, nifty_ltp)
                        sm.enter_level2(opt_price)
                        sm._last_entry_minute = minute_idx
                    elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty < r3 and nifty_ltp >= r3:
                        opt_price = get_opt_ltp(side, nifty_ltp)
                        sm.enter_level3(opt_price)
                        sm._last_entry_minute = minute_idx
                else: # CE
                    if sm.state == State.IDLE and sm.can_enter_level1() and prev_nifty is not None and prev_nifty > s1 and nifty_ltp <= s1:
                        l1_entry_nifty[side] = nifty_ltp
                        sm.enter_level1("NIFTY_MOCK_CE", int(s1), date_str, Decimal("100.0"))
                        sm._entry_time_str = time_str
                        sm._last_entry_minute = minute_idx
                    elif sm.state == State.L1_ENTERED and sm.can_enter_level2() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s2 and nifty_ltp <= s2:
                        opt_price = get_opt_ltp(side, nifty_ltp)
                        sm.enter_level2(opt_price)
                        sm._last_entry_minute = minute_idx
                    elif sm.state == State.L2_ENTERED and sm.can_enter_level3() and cooldown_elapsed and prev_nifty is not None and prev_nifty > s3 and nifty_ltp <= s3:
                        opt_price = get_opt_ltp(side, nifty_ltp)
                        sm.enter_level3(opt_price)
                        sm._last_entry_minute = minute_idx

        prev_nifty = nifty_ltp
        
    return trades

def compute_statistics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute summary statistics for a given set of trades."""
    if not trades:
        return {
            "total_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "average_profit": 0.0,
            "average_loss": 0.0,
            "max_drawdown": 0.0
        }
        
    total_pnl = sum(t["pnl"] for t in trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] <= 0]
    
    win_rate = len(winning_trades) / len(trades) if trades else 0.0
    avg_profit = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
    avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0.0
    
    # Calculate Max Drawdown
    cumulative_pnl = 0.0
    peak = 0.0
    max_drawdown = 0.0
    
    # Sort trades by date + time
    sorted_trades = sorted(trades, key=lambda x: (x["date"], x["exit_time"]))
    
    for t in sorted_trades:
        cumulative_pnl += t["pnl"]
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            
    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate, 4),
        "average_profit": round(avg_profit, 2),
        "average_loss": round(avg_loss, 2),
        "max_drawdown": round(max_drawdown, 2)
    }

def run_destiny_single_backtest(
    date_str: str,
    nifty_prices: List[float],
    config: Dict[str, Any],
    option_prices: Optional[Dict[str, List[Optional[float]]]] = None,
) -> List[Dict[str, Any]]:
    """
    Replay a single day's prices specifically for Destiny Strategy.
    - Resistance R (r1) and Support S (s1)
    - Option B: Maximum 1 trade total per day
    - Target 30 pts, SL 30 pts, 3:20 PM Cutoff
    - The option is the one the engine would buy: PE = ATM+50, CE = ATM-50, on the
      Tuesday-rule expiry
    - SL is a fixed premium floor; TARGET is a flat exit, or (opt-in) a repeating
      ratchet that locks the floor at target and raises it every further
      ratchet_step_points, closing only once premium falls below the floor

    Premium comes from `option_prices` (symbol -> minute closes, recorded from Kite)
    when the traded contract is in it, otherwise from a Black-Scholes model at
    `model_iv_percent`. Each trade says which one it used in `premium_source`.
    Exits fill at the exact line crossed (SL / target / locked floor), not the
    observed premium that crossed it.
    """
    if not nifty_prices:
        return []

    r_level = Decimal(str(config["r1"])) if "r1" in config and config["r1"] else None
    s_level = Decimal(str(config["s1"])) if "s1" in config and config["s1"] else None
    # Opt-out, same as the live engine: None/True/missing all mean enabled - only an
    # explicit False disables that side's entries.
    r_level_enabled = config.get("r_level_enabled") is not False
    s_level_enabled = config.get("s_level_enabled") is not False
    target_pts = Decimal(str(config.get("target_points", 30.0)))
    sl_pts = Decimal(str(config.get("sl_points", 30.0)))
    lot_size = config.get("lot_size", 75)
    model_iv = float(config.get("model_iv_percent") or DEFAULT_IV * 100) / 100.0
    # Opt-in, same as the live engine: None/blank/0/garbage all keep today's flat
    # target exit unchanged. Parse-then-check (not a truthiness check) so a string
    # "0" is recognized as off too, not just the literal number 0.
    ratchet_step_pts = None
    _raw_ratchet = config.get("ratchet_step_points")
    if _raw_ratchet not in (None, ""):
        try:
            _parsed_ratchet = Decimal(str(_raw_ratchet))
            ratchet_step_pts = _parsed_ratchet if _parsed_ratchet > 0 else None
        except Exception:
            ratchet_step_pts = None

    trades = []
    active_trade = None
    trade_taken_today = False

    sq_time_str = config.get("squareoff_time", "15:20")
    try:
        sq_h, sq_m = map(int, sq_time_str.split(":"))
    except Exception:
        sq_h, sq_m = 15, 20
    sq_minutes = sq_h * 60 + sq_m
    no_entry_minutes = _no_entry_minutes(config.get("no_entry_time"), sq_minutes)

    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    expiry = get_expiry_date(trade_date)

    def premium_at(t_info, minute_idx, nifty_ltp) -> Decimal:
        series = t_info["real_series"]
        if series is not None:
            price = series[minute_idx] if minute_idx < len(series) else None
            if price is not None and price > 0:
                t_info["last_price"] = Decimal(str(price))
            return t_info["last_price"]  # no candle yet/any more: hold the last known premium
        return Decimal(str(model_premium(
            t_info["side"], float(nifty_ltp), t_info["strike"], expiry, trade_date, minute_idx, model_iv
        )))

    def close_trade(t_info, exit_price, exit_reason, exit_time):
        pnl = (exit_price - t_info["entry_price"]) * Decimal(str(t_info["qty"]))
        trades.append({
            "date": date_str,
            "side": t_info["side"],
            "level": t_info["level"],
            "symbol": t_info["symbol"],
            "strike": t_info["strike"],
            "lots": 1,
            "qty": t_info["qty"],
            "entry_time": t_info["entry_time"],
            "entry_price": float(t_info["entry_price"]),
            "exit_time": exit_time,
            "exit_price": float(exit_price),
            "exit_reason": exit_reason,
            "locked_floor": float(t_info["locked_floor"]) if t_info.get("locked_floor") is not None else None,
            "pnl": float(pnl),
            "premium_source": t_info["premium_source"],
        })

    prev_nifty = None

    for minute_idx, price in enumerate(nifty_prices):
        nifty_ltp = Decimal(str(price))
        hour = 9 + (minute_idx + 15) // 60
        minute = (minute_idx + 15) % 60
        time_str = f"{hour:02d}:{minute:02d}:00"
        current_minutes = hour * 60 + minute

        # 1. 3:20 PM Square Off Cutoff
        if current_minutes >= sq_minutes:
            if active_trade:
                opt_price = premium_at(active_trade, minute_idx, nifty_ltp)
                close_trade(active_trade, opt_price, "SQUAREOFF", time_str)
                active_trade = None
            break

        # 2. Check Active Trade Target / SL Exits
        if active_trade and ratchet_step_pts is None:
            # Legacy behavior, unchanged: flat exit the instant target is reached.
            opt_price = premium_at(active_trade, minute_idx, nifty_ltp)
            target_price = active_trade["entry_price"] + target_pts
            sl_price = active_trade["entry_price"] - sl_pts

            if opt_price >= target_price:
                close_trade(active_trade, target_price, "TARGET", time_str)
                active_trade = None
            elif opt_price <= sl_price:
                close_trade(active_trade, sl_price, "SL", time_str)
                active_trade = None
        elif active_trade:
            # Ratchet opted in — replays _check_active_trade_exits exactly: SL is a fixed
            # floor checked first (unconditionally); target locks a floor instead of
            # exiting and climbs it by ratchet_step_pts on every further milestone,
            # closing only once premium drops below the current floor. Fills use the
            # exact line crossed (SL / locked floor), same as the legacy branch above.
            opt_price = premium_at(active_trade, minute_idx, nifty_ltp)
            sl_price = active_trade["entry_price"] - sl_pts

            if opt_price <= sl_price:
                close_trade(active_trade, sl_price, "SL", time_str)
                active_trade = None
            else:
                target_price = active_trade["entry_price"] + target_pts
                floor = active_trade.get("locked_floor")
                if floor is None and opt_price >= target_price:
                    floor = target_price
                    active_trade["locked_floor"] = floor
                elif floor is not None and opt_price < floor:
                    close_trade(active_trade, floor, "TARGET", time_str)
                    active_trade = None
                    floor = None
                # Climb regardless of whether the floor was just armed above or was
                # already set from an earlier bar — a 1-minute bar can span several
                # ratchet steps at once (the live engine checks on every tick, far
                # finer-grained), so climb all of them in this same bar rather than
                # waiting for the next one to catch up.
                if active_trade and floor is not None:
                    while opt_price >= floor + ratchet_step_pts:
                        floor += ratchet_step_pts
                    active_trade["locked_floor"] = floor

        # 3. Check Fresh Entry if no trade taken today and no active trade
        # (and, when the user configured a no-entry time, only before that cutoff)
        if not active_trade and not trade_taken_today and (
            no_entry_minutes is None or current_minutes < no_entry_minutes
        ):
            side = None
            level = None
            # PE Entry at Resistance R
            if r_level and r_level_enabled and prev_nifty is not None and prev_nifty < r_level and nifty_ltp >= r_level:
                side, level = "PE", "R1"
            # CE Entry at Support S
            elif s_level and s_level_enabled and prev_nifty is not None and prev_nifty > s_level and nifty_ltp <= s_level:
                side, level = "CE", "S1"

            if side:
                strike = get_option_strike(side, nifty_ltp)
                symbol = build_option_symbol(side, strike, expiry)
                series = (option_prices or {}).get(symbol)
                recorded = series[minute_idx] if series and minute_idx < len(series) else None
                use_real = recorded is not None and recorded > 0
                t_info = {
                    "side": side,
                    "level": level,
                    "symbol": symbol,
                    "strike": strike,
                    "real_series": series if use_real else None,
                    "premium_source": "REAL" if use_real else "MODEL",
                    "last_price": None,
                    "qty": lot_size,
                    "entry_time": time_str,
                    "locked_floor": None,
                }
                t_info["entry_price"] = premium_at(t_info, minute_idx, nifty_ltp)
                active_trade = t_info
                trade_taken_today = True

        prev_nifty = nifty_ltp

    return trades


async def run_backtest_workflow(
    kite_service,
    start_date_str: str,
    end_date_str: str,
    config: Dict[str, Any],
    compare_configs: Optional[List[Dict[str, Any]]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Run full backtest workflow, optionally with comparisons."""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    # 1. Fetch Nifty data once for all configs
    spot_sources: Dict[str, str] = {}
    nifty_data = await fetch_historical_nifty(kite_service, start_dt, end_dt, spot_sources)

    # Recorded option prices only make sense against the real NIFTY path they
    # were recorded alongside - never against a simulated one.
    option_data: Dict[str, Dict[str, List[Optional[float]]]] = {}
    if db is not None:
        for date_str in nifty_data:
            if spot_sources.get(date_str) == "REAL":
                option_data[date_str] = load_option_prices(db, datetime.strptime(date_str, "%Y-%m-%d").date())

    def run_config(cfg: Dict[str, Any], default_type: str) -> List[Dict[str, Any]]:
        trades: List[Dict[str, Any]] = []
        is_destiny = cfg.get("strategy_type", default_type) == "DESTINY"
        for date_str, prices in nifty_data.items():
            if is_destiny:
                trades.extend(run_destiny_single_backtest(date_str, prices, cfg, option_data.get(date_str)))
            else:
                trades.extend(run_single_backtest(date_str, prices, cfg))
        return trades

    # 2. Run core config
    st_type = config.get("strategy_type", "PYRAMID")
    core_trades = run_config(config, st_type)
    core_stats = compute_statistics(core_trades)

    premium_counts = {"REAL": 0, "MODEL": 0}
    for t in core_trades:
        if t.get("premium_source") in premium_counts:
            premium_counts[t["premium_source"]] += 1

    results = {
        "primary": {
            "summary": core_stats,
            "trades": core_trades,
            "data_quality": {
                "days": [
                    {
                        "date": date_str,
                        "spot_source": spot_sources.get(date_str, "MOCK"),
                        "option_symbols_recorded": len(option_data.get(date_str, {})),
                    }
                    for date_str in nifty_data
                ],
                "mock_spot_days": sum(1 for s in spot_sources.values() if s != "REAL"),
                "trades_by_premium_source": premium_counts,
            },
        },
        "comparisons": []
    }

    # 3. Run comparison configs
    if compare_configs:
        for idx, alt_config in enumerate(compare_configs):
            alt_trades = run_config(alt_config, st_type)
            results["comparisons"].append({
                "name": alt_config.get("name", f"Config {idx + 1}"),
                "config": alt_config,
                "summary": compute_statistics(alt_trades)
            })

    return results
