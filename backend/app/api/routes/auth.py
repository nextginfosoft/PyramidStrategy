"""
Kite Authentication Routes — Phase 2 Multi-User
OAuth flow: login URL → Kite login page → callback with request_token → access_token
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from loguru import logger
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.models import ApiConfig, User
from app.services.encryption import encrypt, decrypt
from app.services.kite_service import get_user_kite_service
from app.api.routes.session import require_auth
from app.core.engine_manager import engine_manager

router = APIRouter(prefix="/auth", tags=["auth"])


def _load_kite_credentials_from_db(user_id: int) -> bool:
    """
    Load API key/secret from DB and configure user's KiteService.
    Returns True if credentials found and configured.
    """
    with SessionLocal() as db:
        row = db.query(ApiConfig).filter(
            ApiConfig.user_id == user_id,
            ApiConfig.provider == "zerodha",
            ApiConfig.is_active == True,
        ).first()

        user_kite = get_user_kite_service(user_id)

        if not row or not row.api_key_encrypted:
            return False

        try:
            api_key = decrypt(row.api_key_encrypted)
            api_secret = decrypt(row.api_secret_encrypted)
            user_kite.configure(api_key, api_secret)

            # Restore access token if previously stored
            extra = row.extra_config or {}
            access_token_enc = extra.get("access_token_encrypted")
            if access_token_enc:
                access_token = decrypt(access_token_enc)
                user_kite.set_access_token(access_token)

            return True
        except Exception as e:
            logger.error(f"User {user_id}: Failed to load Kite credentials from DB: {e}")
            return False


@router.get("/kite/login")
def kite_login(user: User = Depends(require_auth)):
    """
    Step 1 — Get Kite OAuth login URL for the logged-in user.
    """
    if not _load_kite_credentials_from_db(user.id):
        raise HTTPException(
            status_code=400,
            detail="Zerodha API key/secret not configured. Go to Settings and save them first.",
        )
    try:
        user_kite = get_user_kite_service(user.id)
        login_url = user_kite.get_login_url()
        return {"login_url": login_url}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kite/callback")
@router.get("/kite/callback/")
def kite_callback(request_token: str = Query(...), user_id: Optional[int] = Query(None)):
    """
    Step 2 — OAuth callback. Handled via redirect query.
    Note: We must pass user_id in the redirect URI to associate it back to the correct user.
    """
    if user_id is None:
        try:
            with SessionLocal() as db:
                first_user = db.query(User).order_by(User.id.asc()).first()
                if first_user:
                    user_id = first_user.id
                    logger.warning(f"Kite callback received without user_id. Defaulting to first user: {first_user.username} (id={user_id})")
                else:
                    user_id = 1
                    logger.warning("Kite callback received without user_id and no users in DB. Defaulting to user_id = 1.")
        except Exception as e:
            user_id = 1
            logger.warning(f"Failed to query database for default user_id during callback: {e}. Defaulting to user_id = 1.")

    try:
        user_kite = get_user_kite_service(user_id)
        access_token = user_kite.exchange_token(request_token)

        # Store access token encrypted in DB
        with SessionLocal() as db:
            row = db.query(ApiConfig).filter(
                ApiConfig.user_id == user_id,
                ApiConfig.provider == "zerodha",
                ApiConfig.is_active == True,
            ).first()
            if row:
                extra = dict(row.extra_config or {})
                extra["access_token_encrypted"] = encrypt(access_token)
                row.extra_config = extra
                db.commit()
                logger.info(f"User {user_id}: Kite access_token stored (encrypted) in DB")

        return {
            "status": "authenticated",
            "message": "Kite login successful. You can now start live market data.",
        }

    except Exception as e:
        logger.error(f"User {user_id}: Kite OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/kite/status")
def kite_status(user: User = Depends(require_auth)):
    """Return current Kite connection status for the Settings UI."""
    user_kite = get_user_kite_service(user.id)
    return user_kite.get_status()


@router.post("/kite/validate")
def validate_kite_token(user: User = Depends(require_auth)):
    """Test if the stored access token is still valid."""
    if not _load_kite_credentials_from_db(user.id):
        return {"valid": False, "message": "Kite credentials not configured"}
    user_kite = get_user_kite_service(user.id)
    valid = user_kite.validate_token()
    return {
        "valid": valid,
        "message": "Token valid ✅" if valid else "Token expired — please re-login to Kite",
    }


@router.post("/kite/auto-login")
def kite_auto_login(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    """
    Attempt programmatic auto-login using stored username, password, and TOTP secret.
    """
    row = db.query(ApiConfig).filter(
        ApiConfig.user_id == user.id,
        ApiConfig.provider == "zerodha",
        ApiConfig.is_active == True,
    ).first()

    if not row or not row.extra_config:
        raise HTTPException(
            status_code=400,
            detail="Zerodha credentials not fully configured in settings."
        )

    extra = row.extra_config
    username = extra.get("username")
    password_enc = extra.get("password_encrypted")
    totp_secret_enc = extra.get("totp_secret_encrypted")

    if not username or not password_enc or not totp_secret_enc:
        raise HTTPException(
            status_code=400,
            detail="Automated login requires Username, Password, and TOTP Secret Key."
        )

    if not _load_kite_credentials_from_db(user.id):
        raise HTTPException(status_code=400, detail="Zerodha API key/secret not configured.")

    try:
        password = decrypt(password_enc)
        totp_secret = decrypt(totp_secret_enc)
        
        user_kite = get_user_kite_service(user.id)
        access_token = user_kite.auto_login(username, password, totp_secret)

        # Store access token encrypted in DB
        extra_updated = dict(row.extra_config or {})
        extra_updated["access_token_encrypted"] = encrypt(access_token)
        row.extra_config = extra_updated
        db.commit()

        logger.info(f"User {user.id}: Programmatic daily login successful!")
        return {
            "status": "authenticated",
            "message": "Programmatic daily login successful! Access token updated.",
        }
    except Exception as e:
        logger.error(f"User {user.id}: Programmatic login failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Automated login failed: {str(e)}"
        )


@router.post("/kite/start-feed")
async def start_live_feed(user: User = Depends(require_auth)):
    """
    Start KiteTicker WebSocket for live NIFTY market data for this user.
    """
    user_engine = engine_manager.get_engine(user.id)
    user_kite = get_user_kite_service(user.id)

    if not _load_kite_credentials_from_db(user.id):
        raise HTTPException(status_code=400, detail="Kite not configured")

    if not user_kite.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated — complete Kite OAuth login first",
        )

    if user_kite._ticker_running:
        return {"status": "already_running", "message": "Live feed already active"}

    try:
        loop = asyncio.get_event_loop()
        user_kite.start_ticker(
            on_nifty_tick=user_engine.on_nifty_tick,
            on_option_tick=user_engine.on_option_tick,
            loop=loop,
        )
        logger.info(f"User {user.id}: Live NIFTY feed started via API request")
        return {
            "status": "started",
            "message": "Live NIFTY feed started. Strategy engine will use real prices.",
        }
    except Exception as e:
        logger.error(f"User {user.id}: Failed to start live feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kite/stop-feed")
def stop_live_feed(user: User = Depends(require_auth)):
    """Stop KiteTicker."""
    user_kite = get_user_kite_service(user.id)
    user_kite.stop_ticker()
    return {"status": "stopped", "message": "Live feed stopped"}


@router.post("/kite/load-instruments")
def load_instruments(user: User = Depends(require_auth)):
    """Manually trigger NFO instrument cache reload."""
    user_kite = get_user_kite_service(user.id)
    if not user_kite.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_kite.load_instruments()
    return {
        "status": "loaded",
        "instruments_loaded": user_kite._instruments_loaded,
        "message": "NFO instrument cache refreshed",
    }


@router.post("/kite/logout")
def kite_logout(user: User = Depends(require_auth)):
    """Clear access token and stop live feed."""
    user_kite = get_user_kite_service(user.id)
    user_kite.clear_credentials()

    # Remove access token from DB
    with SessionLocal() as db:
        row = db.query(ApiConfig).filter(
            ApiConfig.user_id == user.id,
            ApiConfig.provider == "zerodha",
            ApiConfig.is_active == True,
        ).first()
        if row:
            extra = dict(row.extra_config or {})
            extra.pop("access_token_encrypted", None)
            row.extra_config = extra
            db.commit()

    logger.info(f"User {user.username}: Kite logged out — access token cleared")
    return {"status": "logged_out"}
