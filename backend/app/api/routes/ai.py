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

from app.services.ai_service import get_user_ai_service
from app.db.database import SessionLocal, get_db
from app.models.models import AISuggestion, User
from app.core.time_rules import today_ist
from app.api.routes.session import require_auth

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
