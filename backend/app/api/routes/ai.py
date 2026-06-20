"""
AI Observer Routes — Phase 3 Multi-User
GET  /ai/suggestions        — today's AI suggestions
GET  /ai/suggestions/history — past N days
POST /ai/test               — test AI provider connection
POST /ai/reload             — reload AI config from DB
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from loguru import logger
from datetime import timedelta
from sqlalchemy.orm import Session

from app.services.ai_service import get_user_ai_service
from app.db.database import SessionLocal, get_db
from app.models.models import AISuggestion, User
from app.core.time_rules import today_ist
from app.api.routes.session import require_auth
from app.core.engine_manager import engine_manager
from app.services.kite_service import get_user_kite_service

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
    """Generate pre-market AI brief containing VIX analysis, expected range, optimal R/S suggest and quality score."""
    ai_service = get_user_ai_service(user.id)
    user_engine = engine_manager.get_engine(user.id)
    user_status = user_engine.get_full_status()
    nifty_ltp = user_status.get("nifty_ltp") or 23150.0  # fallback to mock close if none
    
    # Load config from DB
    from app.models.models import StrategyConfig
    cfg = db.query(StrategyConfig).filter(
        StrategyConfig.user_id == user.id,
        StrategyConfig.is_active == True
    ).first()
    
    if not cfg:
        config_dict = {"s1": 23100.0, "s2": 23050.0, "s3": 23000.0, "r1": 23200.0, "r2": 23250.0, "r3": 23300.0}
    else:
        config_dict = {
            "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
            "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        }
        
    user_kite = get_user_kite_service(user.id)
    vix = user_kite.get_india_vix()
    
    brief = await ai_service.generate_pre_market_brief(nifty_ltp, vix, config_dict)
    return brief


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
