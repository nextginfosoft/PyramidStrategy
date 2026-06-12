"""
Notification Routes — Phase 3
POST /notifications/test   — send a test Telegram message
GET  /notifications/status — Telegram service status
POST /notifications/reload — reload Telegram config from DB
"""

from fastapi import APIRouter
from loguru import logger

from app.services.notification import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def test_telegram():
    """Send a test Telegram message to verify bot token + chat ID."""
    if not notification_service.is_enabled():
        return {
            "success": False,
            "message": "Telegram not configured — save Bot Token and Chat ID in Settings first",
        }
    success, message = await notification_service.test_connection()
    return {"success": success, "message": message}


@router.get("/status")
def notification_status():
    """Return current notification service status."""
    return {
        "telegram_enabled": notification_service.is_enabled(),
    }


@router.post("/reload")
def reload_notifications():
    """Reload Telegram config from DB."""
    notification_service.load_from_db()
    return {
        "status": "reloaded",
        "enabled": notification_service.is_enabled(),
    }
