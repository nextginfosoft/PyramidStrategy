import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.api.routes.session import require_auth
from app.db.database import get_db
from app.models.models import User
from app.services.kite_service import get_user_kite_service
from app.services.backtesting import run_backtest_workflow
from app.services.option_history import (
    MAX_BACKFILL_DAYS,
    backfill_range,
    recorded_symbol_counts,
    weekdays_between,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])

class BacktestConfigSchema(BaseModel):
    r1: float
    r2: Optional[float] = 0.0
    r3: Optional[float] = 0.0
    s1: float
    s2: Optional[float] = 0.0
    s3: Optional[float] = 0.0
    lot_size: int = 75
    target_points: float = 20.0
    sl_points: float = 10.0
    squareoff_time: Optional[str] = "11:30"
    no_entry_time: Optional[str] = None
    ratchet_step_points: Optional[float] = None
    # Destiny only: implied volatility (%) for the option-price model, used on
    # days with no recorded option prices.
    model_iv_percent: float = Field(14.0, gt=0, le=200)
    # Destiny only, opt-out. None/True = enabled; only an explicit False disables
    # that side's entries, same convention as the live config.
    r_level_enabled: Optional[bool] = None
    s_level_enabled: Optional[bool] = None
    strategy_type: Optional[str] = "PYRAMID"
    name: Optional[str] = "Primary"

class BacktestRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    config: BacktestConfigSchema
    compare_configs: Optional[List[BacktestConfigSchema]] = None

class OptionHistoryRange(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD

@router.post("")
async def run_backtest(
    req: BacktestRequest,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    kite_service = get_user_kite_service(user.id)
    try:
        results = await run_backtest_workflow(
            kite_service=kite_service,
            start_date_str=req.start_date,
            end_date_str=req.end_date,
            config=req.config.model_dump(),
            compare_configs=[c.model_dump() for c in req.compare_configs] if req.compare_configs else None,
            db=db,
        )
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {str(e)}")


def _parse_range(start_date: str, end_date: str) -> tuple[date, date]:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD.")
    if end < start:
        raise HTTPException(status_code=400, detail="End date is before the start date.")
    return start, end


@router.get("/option-history")
def option_history_coverage(
    start_date: str,
    end_date: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Which weekdays in the range have recorded option prices, and for how many contracts."""
    start, end = _parse_range(start_date, end_date)
    counts = recorded_symbol_counts(db, start, end)
    return {
        "days": [
            {"date": d.isoformat(), "symbols": counts.get(d, 0)}
            for d in weekdays_between(start, end)
        ]
    }


@router.post("/option-history/backfill")
async def backfill_option_history(
    req: OptionHistoryRange,
    user: User = Depends(require_auth),
):
    """
    Fetch real option prices from Kite for recent past days and store them.
    Only works for days whose weekly contract is still listed on Kite (it
    expires within a week of the day) - older days come back as missing.
    """
    start, end = _parse_range(req.start_date, req.end_date)
    if len(weekdays_between(start, end)) > MAX_BACKFILL_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Fetch at most {MAX_BACKFILL_DAYS} trading days at a time.",
        )
    kite_service = get_user_kite_service(user.id)
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=400, detail="Log in to Kite first - option prices come from Kite.")

    loop = asyncio.get_running_loop()
    try:
        days = await loop.run_in_executor(None, backfill_range, kite_service, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetching option prices failed: {e}")
    return {"days": days}
