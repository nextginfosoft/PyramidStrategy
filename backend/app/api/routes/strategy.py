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
    }

    # Run safety checks before starting (especially important for live mode)
    from app.core.safety_checks import run_safety_checks
    user_kite = get_user_kite_service(user.id)

    passed, errors, warnings = run_safety_checks(
        paper_trade=settings.PAPER_TRADE,
        kite_service=user_kite,
        strategy_config=config_dict,
    )

    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"message": "Safety checks failed — cannot start strategy", "errors": errors},
        )

    # Wire KiteService into OrderManager for live trading
    if not settings.PAPER_TRADE:
        user_engine.order_manager.kite = user_kite
        user_engine.order_manager.paper_trade = False

    user_engine.load_config(config_dict)
    user_engine.start()

    # Broadcast status immediately so frontend updates state to running
    nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
    await user_engine._broadcast_status(nifty_price)

    # Start mock feed in background (paper trade mode only)
    if settings.PAPER_TRADE:
        background_tasks.add_task(_run_mock_feed, user.id)

    return {
        "status": "started",
        "paper_trade": settings.PAPER_TRADE,
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


@router.post("/reset-daily")
def daily_reset(user: User = Depends(require_auth)):
    """Manual daily reset."""
    user_engine = engine_manager.get_engine(user.id)
    user_engine.daily_reset()
    return {"status": "reset", "message": "Both CE and PE state machines reset for new day"}


@router.post("/simulate-tick")
async def simulate_tick(nifty_price: float, user: User = Depends(require_auth)):
    """
    Manually push a NIFTY price tick through the user's strategy engine.
    """
    user_engine = engine_manager.get_engine(user.id)
    await user_engine.on_nifty_tick(Decimal(str(nifty_price)))
    return {"status": "tick_processed", "nifty_price": nifty_price, **user_engine.get_full_status()}


@router.get("/safety-check")
def safety_check(user: User = Depends(require_auth)):
    """Run safety checks without starting. Returns errors and warnings."""
    from app.core.safety_checks import run_safety_checks
    user_engine = engine_manager.get_engine(user.id)
    user_kite = get_user_kite_service(user.id)

    cfg_dict = None
    if user_engine.config:
        cfg_dict = user_engine.config

    passed, errors, warnings = run_safety_checks(
        paper_trade=settings.PAPER_TRADE,
        kite_service=user_kite,
        strategy_config=cfg_dict,
    )
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "paper_trade": settings.PAPER_TRADE,
    }


async def _run_mock_feed(user_id: int):
    user_engine = engine_manager.get_engine(user_id)
    await user_engine.mock_feed.start()
