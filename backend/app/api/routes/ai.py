"""
AI Observer Routes — Phase 3 Multi-User
GET  /ai/suggestions        — today's AI suggestions
GET  /ai/suggestions/history — past N days
POST /ai/test               — test AI provider connection
POST /ai/reload             — reload AI config from DB
"""

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from loguru import logger
from datetime import timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.services.ai_service import get_user_ai_service, run_pre_market_brief_for_user
from app.db.database import SessionLocal, get_db
from app.models.models import AISuggestion, User, PreMarketBrief, StrategyConfig
from app.core.time_rules import today_ist
from app.api.routes.session import require_auth
from app.core.engine_manager import engine_manager
from app.services.kite_service import get_user_kite_service
from app.core.safety_checks import run_safety_checks
from app.api.routes.strategy import _run_mock_feed

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/suggestions")
def get_today_suggestions(limit: int = Query(20, le=100), user: User = Depends(require_auth)):
    """Return today's AI suggestions ordered newest first."""
    ai_service = get_user_ai_service(user.id)
    return ai_service.get_today_suggestions(limit=limit)


@router.get("/suggestions/history")
def get_suggestions_history(days: int = Query(7, le=30), user: User = Depends(require_auth)):
    """Return AI suggestions for the last N days."""
    from_date = today_ist() - timedelta(days=days)
    try:
        with SessionLocal() as db:
            rows = (
                db.query(AISuggestion)
                .filter(AISuggestion.user_id == user.id, AISuggestion.trade_date >= from_date)
                .order_by(AISuggestion.created_at.desc())
                .limit(100)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "trade_date": str(r.trade_date),
                    "event": r.event,
                    "side": r.side,
                    "level": r.level,
                    "nifty_ltp": float(r.nifty_ltp) if r.nifty_ltp else None,
                    "provider": r.provider,
                    "suggestion": r.suggestion,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_ai_connection(user: User = Depends(require_auth)):
    """Test AI API key by making a real (minimal) call."""
    ai_service = get_user_ai_service(user.id)
    if not ai_service.is_enabled():
        return {"success": False, "message": "AI not configured — save API key in Settings first"}
    success, message = await ai_service.test_connection()
    return {"success": success, "message": message, "provider": ai_service._provider}


@router.post("/reload")
def reload_ai_config(user: User = Depends(require_auth)):
    """Reload AI config from DB."""
    ai_service = get_user_ai_service(user.id)
    ai_service.load_from_db()
    return {
        "status": "reloaded",
        "enabled": ai_service.is_enabled(),
        "provider": ai_service._provider,
    }


@router.get("/status")
def ai_status(user: User = Depends(require_auth)):
    """Return current AI service status."""
    ai_service = get_user_ai_service(user.id)
    return {
        "enabled": ai_service.is_enabled(),
        "provider": ai_service._provider,
        "api_key_set": ai_service._api_key is not None,
    }


@router.get("/brief/pre-market")
async def get_pre_market_brief(
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Generate or retrieve pre-market AI brief containing VIX, Expected Range, Level critiques and optimal configuration suggestions."""
    today = today_ist()
    
    # Try fetching cached brief from DB first
    brief_row = db.query(PreMarketBrief).filter(
        PreMarketBrief.user_id == user.id,
        PreMarketBrief.trade_date == today
    ).first()
    
    if brief_row:
        return {
            "success": True,
            "vix": float(brief_row.vix) if brief_row.vix else 13.5,
            "vix_analysis": brief_row.vix_analysis,
            "expected_range": brief_row.expected_range,
            "level_assessment": brief_row.level_assessment,
            "suggested_config": brief_row.suggested_config,
            "quality_score": brief_row.quality_score,
            "quality_reason": brief_row.quality_reason,
            "pcr": float(brief_row.pcr) if brief_row.pcr else None,
            "max_pain": float(brief_row.max_pain) if brief_row.max_pain else None,
            "ce_wall": float(brief_row.ce_wall) if brief_row.ce_wall else None,
            "pe_wall": float(brief_row.pe_wall) if brief_row.pe_wall else None,
            "opening_gap": float(brief_row.opening_gap) if brief_row.opening_gap else 0.0,
            "approved": brief_row.approved
        }
        
    # Fallback: run generation dynamically if not already cached
    brief = await run_pre_market_brief_for_user(db, user.id, today)
    if brief.get("success"):
        brief["approved"] = False
    return brief


@router.post("/brief/pre-market/approve")
async def approve_pre_market_brief(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Approve suggested configurations and arm the strategy engine."""
    today = today_ist()
    
    brief = db.query(PreMarketBrief).filter(
        PreMarketBrief.user_id == user.id,
        PreMarketBrief.trade_date == today
    ).first()
    
    if not brief:
        raise HTTPException(status_code=400, detail="No pre-market AI brief found for today. Generate or view it first.")
        
    if not brief.suggested_config:
        raise HTTPException(status_code=400, detail="No suggested configuration levels found in today's brief.")
        
    # Mark as approved
    brief.approved = True
    
    # Load and update active StrategyConfig
    cfg = db.query(StrategyConfig).filter(
        StrategyConfig.user_id == user.id,
        StrategyConfig.is_active == True
    ).first()
    
    if not cfg:
        raise HTTPException(status_code=400, detail="No active strategy config found to update.")
        
    sugg = brief.suggested_config
    cfg.s1 = Decimal(str(sugg["s1"]))
    cfg.s2 = Decimal(str(sugg["s2"]))
    cfg.s3 = Decimal(str(sugg["s3"]))
    cfg.r1 = Decimal(str(sugg["r1"]))
    cfg.r2 = Decimal(str(sugg["r2"]))
    cfg.r3 = Decimal(str(sugg["r3"]))
    if "recommended_lots" in sugg:
        cfg.lot_size = int(sugg["recommended_lots"])
        
    db.commit()
    logger.info(f"User {user.username} approved pre-market levels. StrategyConfig updated.")
    
    # Arm the Strategy Engine
    user_engine = engine_manager.get_engine(user.id)
    if user_engine.is_running:
        return {
            "success": True,
            "message": "Suggested configurations applied. Strategy was already running.",
            "strategy_status": "running",
            "approved": True
        }
        
    config_dict = {
        "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
        "lot_size": cfg.lot_size,
        "target_points": float(cfg.target_points),
        "sl_points": float(cfg.sl_points),
        "paper_trade": cfg.paper_trade,
    }
    
    user_kite = get_user_kite_service(user.id)
    passed, errors, warnings = run_safety_checks(
        paper_trade=cfg.paper_trade,
        kite_service=user_kite,
        strategy_config=config_dict,
    )
    
    if not passed:
        raise HTTPException(
            status_code=400,
            detail={"message": "Safety checks failed — cannot arm strategy", "errors": errors},
        )
        
    user_engine.order_manager.paper_trade = cfg.paper_trade
    if not cfg.paper_trade:
        user_engine.order_manager.kite = user_kite
    else:
        user_engine.order_manager.kite = None
        
    user_engine.mock_mode = cfg.paper_trade
    user_engine.load_config(config_dict)
    user_engine.start()
    
    # Broadcast strategy status
    nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
    await user_engine._broadcast_status(nifty_price)
    
    if cfg.paper_trade and not user_kite._ticker_running:
        background_tasks.add_task(_run_mock_feed, user.id)
        
    return {
        "success": True,
        "message": "Suggested configurations applied and strategy armed successfully!",
        "strategy_status": "started",
        "warnings": warnings,
        "approved": True
    }


@router.get("/brief/post-session")
async def get_post_session_review(
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Generate post-session review analyzing today's performance, what worked, and future recommendations."""
    ai_service = get_user_ai_service(user.id)
    
    # Fetch today's trades and P&L
    from app.api.routes.trades import get_today_trades, get_today_pnl
    trades = get_today_trades(db, user)
    pnl = get_today_pnl(db, user)
    
    # Format trades for AI
    trades_list = []
    for t in trades:
        trades_list.append({
            "id": t.id,
            "side": t.side,
            "level": t.level,
            "action": t.action,
            "avg_price": float(t.avg_price) if t.avg_price else None,
            "pnl": float(t.pnl) if t.pnl else None,
        })
        
    review = await ai_service.generate_post_session_review(trades_list, pnl)
    return review


@router.post("/quotes/refresh")
async def refresh_ai_quotes(user: User = Depends(require_auth)):
    """Manually trigger AI daily motivational quotes generation for gamification."""
    from app.gamification.ai_quotes import generate_daily_ai_quotes
    success = await generate_daily_ai_quotes(user_id=user.id)
    if not success:
        return {
            "status": "warning",
            "message": "AI generation skipped or failed (check if AI Provider API key is configured). Hardcoded quotes remain active."
        }
    return {
        "status": "success",
        "message": "AI daily quotes successfully generated and loaded into gamification engine!"
    }
