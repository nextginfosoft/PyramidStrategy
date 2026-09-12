from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.api.routes.session import require_auth
from app.models.models import User
from app.services.kite_service import get_user_kite_service
from app.services.backtesting import run_backtest_workflow

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
    strategy_type: Optional[str] = "PYRAMID"
    name: Optional[str] = "Primary"

class BacktestRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    config: BacktestConfigSchema
    compare_configs: Optional[List[BacktestConfigSchema]] = None

@router.post("")
async def run_backtest(
    req: BacktestRequest,
    user: User = Depends(require_auth)
):
    kite_service = get_user_kite_service(user.id)
    try:
        results = await run_backtest_workflow(
            kite_service=kite_service,
            start_date_str=req.start_date,
            end_date_str=req.end_date,
            config=req.config.model_dump(),
            compare_configs=[c.model_dump() for c in req.compare_configs] if req.compare_configs else None
        )
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {str(e)}")
