from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import StrategyConfig
from app.core.strategy_engine import engine
from app.services.mock_feed import mock_feed
from app.config import settings
import asyncio

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/status")
def get_status():
    return engine.get_full_status()


@router.post("/start")
async def start_strategy(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if engine.is_running:
        raise HTTPException(status_code=400, detail="Strategy is already running")

    # Load config from DB
    cfg = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).first()
    if not cfg:
        raise HTTPException(status_code=400, detail="No active strategy config found. Set levels first.")

    engine.load_config({
        "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
        "lot_size": cfg.lot_size,
        "target_points": float(cfg.target_points),
        "sl_points": float(cfg.sl_points),
    })
    engine.start()

    # Start mock feed in background (paper trade mode)
    if settings.PAPER_TRADE:
        background_tasks.add_task(_run_mock_feed)

    return {"status": "started", "paper_trade": settings.PAPER_TRADE}


@router.post("/stop")
def stop_strategy():
    engine.stop()
    mock_feed.stop()
    return {"status": "stopped"}


@router.post("/reset-daily")
def daily_reset():
    """Manual daily reset (also runs automatically at 9:00 AM via scheduler)."""
    engine.daily_reset()
    return {"status": "reset", "message": "Both CE and PE state machines reset for new day"}


@router.post("/simulate-tick")
async def simulate_tick(nifty_price: float):
    """
    Manually push a NIFTY price tick through the strategy engine.
    Useful for testing without the mock feed running.
    """
    from decimal import Decimal
    await engine.on_nifty_tick(Decimal(str(nifty_price)))
    return {"status": "tick_processed", "nifty_price": nifty_price, **engine.get_full_status()}


async def _run_mock_feed():
    await mock_feed.start()
