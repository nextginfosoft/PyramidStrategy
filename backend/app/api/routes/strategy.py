from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal

from app.db.database import get_db
from app.models.models import StrategyConfig, User
from app.core.engine_manager import engine_manager
from app.services.kite_service import get_user_kite_service
from app.api.routes.session import require_auth
from app.config import settings
from loguru import logger

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/status")
def get_status(user: User = Depends(require_auth)):
    user_engine = engine_manager.get_engine(user.id)
    return user_engine.get_full_status()


@router.post("/start")
async def start_strategy(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    user_engine = engine_manager.get_engine(user.id)
    if user_engine.is_running:
        raise HTTPException(status_code=400, detail="Strategy is already running")

    # Load config from DB for this user
    cfg = db.query(StrategyConfig).filter(
        StrategyConfig.user_id == user.id,
        StrategyConfig.is_active == True
    ).first()
    if not cfg:
        raise HTTPException(status_code=400, detail="No active strategy config found. Set levels first.")

    config_dict = {
        "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
        "lot_size": cfg.lot_size,
        "target_points": float(cfg.target_points),
        "sl_points": float(cfg.sl_points),
        "paper_trade": cfg.paper_trade,
        "squareoff_time": cfg.squareoff_time or "11:30",
    }

    # Run safety checks before starting (especially important for live mode)
    from app.core.safety_checks import run_safety_checks
    user_kite = get_user_kite_service(user.id)

    passed, errors, warnings = run_safety_checks(
        paper_trade=cfg.paper_trade,
        kite_service=user_kite,
        strategy_config=config_dict,
    )

    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"message": "Safety checks failed — cannot start strategy", "errors": errors},
        )

    # Wire KiteService into OrderManager for live trading
    user_engine.order_manager.paper_trade = cfg.paper_trade
    if not cfg.paper_trade:
        user_engine.order_manager.kite = user_kite
    else:
        user_engine.order_manager.kite = None

    user_engine.mock_mode = cfg.paper_trade
    user_engine.load_config(config_dict)
    user_engine.start()

    # Seed initial NIFTY price from REST API if not yet received via WebSocket ticks
    if not user_engine.last_nifty_price and user_kite.is_authenticated():
        try:
            spot_price = user_kite.get_nifty_spot_ltp()
            if spot_price:
                await user_engine.on_nifty_tick(spot_price)
        except Exception as seed_err:
            logger.warning(f"Failed to seed initial NIFTY price on start: {seed_err}")

    # Broadcast status immediately so frontend updates state to running
    nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
    await user_engine._broadcast_status(nifty_price)

    # Start mock feed in background (paper trade mode only if live feed is not active)
    if cfg.paper_trade and not user_kite._ticker_running:
        background_tasks.add_task(_run_mock_feed, user.id)

    return {
        "status": "started",
        "paper_trade": cfg.paper_trade,
        "warnings": warnings,
    }


@router.post("/stop")
async def stop_strategy(user: User = Depends(require_auth)):
    user_engine = engine_manager.get_engine(user.id)
    user_engine.stop()
    user_engine.mock_feed.stop()

    # Broadcast status immediately so frontend knows it is stopped
    nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
    await user_engine._broadcast_status(nifty_price)
    return {"status": "stopped"}


@router.post("/emergency-exit")
async def emergency_exit(user: User = Depends(require_auth)):
    user_engine = engine_manager.get_engine(user.id)
    res = await user_engine.emergency_exit()

    # Broadcast status immediately so frontend knows it is stopped
    nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
    await user_engine._broadcast_status(nifty_price)
    return res



@router.post("/reset-daily")
def daily_reset(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    """Manual daily reset."""
    from app.models.models import Trade, DailyPnL, AISuggestion, AuditLog
    from app.core.time_rules import today_ist
    from sqlalchemy import func

    # 1. Reset strategy engine in-memory state
    user_engine = engine_manager.get_engine(user.id)
    user_engine.daily_reset()

    # 2. Clear database records for today (to clear dashboard views)
    today = today_ist()
    try:
        db.query(Trade).filter(Trade.user_id == user.id, Trade.trade_date == today).delete()
        db.query(DailyPnL).filter(DailyPnL.user_id == user.id, DailyPnL.trade_date == today).delete()
        db.query(AISuggestion).filter(AISuggestion.user_id == user.id, AISuggestion.trade_date == today).delete()
        
        # Clear audit logs created today for this user
        db.query(AuditLog).filter(
            AuditLog.user_id == user.id,
            func.date(AuditLog.created_at) == today
        ).delete()
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database clear failed on reset: {str(e)}")

    return {"status": "reset", "message": "Both CE and PE state machines reset and database records cleared for today"}


@router.post("/simulate-tick")
async def simulate_tick(nifty_price: float, user: User = Depends(require_auth)):
    """
    Manually push a NIFTY price tick through the user's strategy engine.
    """
    user_engine = engine_manager.get_engine(user.id)
    await user_engine.on_nifty_tick(Decimal(str(nifty_price)))
    return {"status": "tick_processed", "nifty_price": nifty_price, **user_engine.get_full_status()}


@router.get("/safety-check")
def safety_check(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    """Run safety checks without starting. Returns errors and warnings."""
    from app.core.safety_checks import run_safety_checks
    user_engine = engine_manager.get_engine(user.id)
    user_kite = get_user_kite_service(user.id)

    cfg = db.query(StrategyConfig).filter(
        StrategyConfig.user_id == user.id,
        StrategyConfig.is_active == True
    ).first()

    paper_trade = cfg.paper_trade if cfg else settings.PAPER_TRADE
    cfg_dict = None
    if cfg:
        cfg_dict = {
            "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
            "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
            "lot_size": cfg.lot_size,
            "target_points": float(cfg.target_points),
            "sl_points": float(cfg.sl_points),
            "paper_trade": cfg.paper_trade,
            "squareoff_time": cfg.squareoff_time or "11:30",
        }
    elif user_engine.config:
        cfg_dict = user_engine.config

    passed, errors, warnings = run_safety_checks(
        paper_trade=paper_trade,
        kite_service=user_kite,
        strategy_config=cfg_dict,
    )
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "paper_trade": paper_trade,
    }


async def _run_mock_feed(user_id: int):
    user_engine = engine_manager.get_engine(user_id)
    await user_engine.mock_feed.start()
