from fastapi import APIRouter, Depends
from loguru import logger

from app.models.models import User
from app.api.routes.session import require_auth
from app.services.notification import get_user_notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def test_telegram(user: User = Depends(require_auth)):
    """Send a test Telegram message to verify bot token + chat ID."""
    ns = get_user_notification_service(user.id)
    if not ns.is_enabled():
        return {
            "success": False,
            "message": "Telegram not configured — save Bot Token and Chat ID in Settings first",
        }
    success, message = await ns.test_connection()
    return {"success": success, "message": message}


@router.get("/status")
def notification_status(user: User = Depends(require_auth)):
    """Return current notification service status."""
    ns = get_user_notification_service(user.id)
    return {
        "telegram_enabled": ns.is_enabled(),
    }


@router.post("/reload")
def reload_notifications(user: User = Depends(require_auth)):
    """Reload Telegram config from DB."""
    ns = get_user_notification_service(user.id)
    ns.load_from_db()
    return {
        "status": "reloaded",
        "enabled": ns.is_enabled(),
    }
