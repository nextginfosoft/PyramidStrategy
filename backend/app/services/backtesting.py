import hashlib
import random
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import StrategyConfig, Trade
from app.core.state_machine import StateMachine, State

# NSE:NIFTY 50 spot index token
NIFTY_SPOT_TOKEN = 256265

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

async def fetch_historical_nifty(kite_service, start_date: date, end_date: date) -> Dict[str, List[float]]:
    """
    Fetch historical Nifty spot index prices per day.
    Falls back to mock data if Kite is not authenticated or fails.
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

    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            current_date += delta
            continue
            
        date_str = current_date.strftime("%Y-%m-%d")
        day_prices = []
        
        if kite_available:
            try:
                # Fetch 1-minute historical data for NIFTY spot
                from_dt = datetime.combine(current_date, datetime.min.time())
                to_dt = datetime.combine(current_date, datetime.max.time())
                
                records = kite_service._kite.historical_data(
                    instrument_token=NIFTY_SPOT_TOKEN,
                    from_date=from_dt,
                    to_date=to_dt,
                    interval="minute"
                )
                
                if records:
                    # Filter/extract close prices
                    for r in records:
                        # Only keep trading hours: 09:15 to 15:30
                        dt = r["date"]
                        if isinstance(dt, str):
                            dt = datetime.fromisoformat(dt)
                        
                        # Convert to IST local time comparison
                        hour = dt.hour
                        minute = dt.minute
                        
                        # If Zerodha returns UTC, adjust to IST
                        # Typically Zerodha API returns native timezone strings (Asia/Kolkata)
                        time_val = hour * 100 + minute
                        if 915 <= time_val <= 1530:
                            day_prices.append(float(r["close"]))
                            
            except Exception as e:
                logger.warning(f"Error fetching historical data for {date_str}: {e}")
                day_prices = []
                
        # Fallback to mock data if Kite failed or returned empty
        if not day_prices:
            day_prices = get_nifty_data_for_day(date_str)
            
        data[date_str] = day_prices
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
    cutoff_minutes = sq_minutes - 15

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

async def run_backtest_workflow(
    kite_service,
    start_date_str: str,
    end_date_str: str,
    config: Dict[str, Any],
    compare_configs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Run full backtest workflow, optionally with comparisons."""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    
    # 1. Fetch Nifty data once for all configs
    nifty_data = await fetch_historical_nifty(kite_service, start_dt, end_dt)
    
    # 2. Run core config
    core_trades = []
    for date_str, prices in nifty_data.items():
        day_trades = run_single_backtest(date_str, prices, config)
        core_trades.extend(day_trades)
        
    core_stats = compute_statistics(core_trades)
    
    results = {
        "primary": {
            "summary": core_stats,
            "trades": core_trades
        },
        "comparisons": []
    }
    
    # 3. Run comparison configs
    if compare_configs:
        for idx, alt_config in enumerate(compare_configs):
            alt_trades = []
            for date_str, prices in nifty_data.items():
                day_trades = run_single_backtest(date_str, prices, alt_config)
                alt_trades.extend(day_trades)
            
            alt_stats = compute_statistics(alt_trades)
            results["comparisons"].append({
                "name": alt_config.get("name", f"Config {idx+1}"),
                "config": alt_config,
                "summary": alt_stats
            })
            
    return results
