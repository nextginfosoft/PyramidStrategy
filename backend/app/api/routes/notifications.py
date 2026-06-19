from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User
from app.api.routes.session import require_auth
from app.services.notification import get_user_notification_service
from app.services.whatsapp import get_user_whatsapp_service
from app.services.reporting import get_user_reporting_config

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


@router.post("/whatsapp/test")
async def test_whatsapp(user: User = Depends(require_auth)):
    """Send a test WhatsApp message to verify Meta / Twilio settings."""
    ws = get_user_whatsapp_service(user.id)
    if not ws.is_enabled():
        return {
            "success": False,
            "message": "WhatsApp not configured — save WhatsApp settings first",
        }
    success, message = await ws.test_connection()
    return {"success": success, "message": message}


@router.get("/status")
def notification_status(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Return current notification and reporting service status."""
    ns = get_user_notification_service(user.id)
    ws = get_user_whatsapp_service(user.id)
    rep_cfg = get_user_reporting_config(user.id, db)
    return {
        "telegram_enabled": ns.is_enabled(),
        "whatsapp_enabled": ws.is_enabled(),
        "reporting_format": rep_cfg.get("format", "telegram"),
    }


@router.post("/reload")
def reload_notifications(user: User = Depends(require_auth)):
    """Reload Telegram and WhatsApp configurations from DB."""
    ns = get_user_notification_service(user.id)
    ws = get_user_whatsapp_service(user.id)
    ns.load_from_db()
    ws.load_from_db()
    return {
        "status": "reloaded",
        "telegram_enabled": ns.is_enabled(),
        "whatsapp_enabled": ws.is_enabled(),
    }
