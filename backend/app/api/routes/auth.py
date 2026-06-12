"""
Kite Authentication Routes — Phase 2
OAuth flow: login URL → Kite login page → callback with request_token → access_token
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.db.database import SessionLocal
from app.models.models import ApiConfig
from app.services.encryption import encrypt, decrypt
from app.services.kite_service import kite_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _load_kite_credentials_from_db() -> bool:
    """
    Load API key/secret from DB and configure KiteService.
    Also restores existing access token if present.
    Returns True if credentials found and configured.
    """
    with SessionLocal() as db:
        row = db.query(ApiConfig).filter(
            ApiConfig.provider == "zerodha",
            ApiConfig.is_active == True,
        ).first()

        if not row or not row.api_key_encrypted:
            return False

        try:
            api_key = decrypt(row.api_key_encrypted)
            api_secret = decrypt(row.api_secret_encrypted)
            kite_service.configure(api_key, api_secret)

            # Restore access token if previously stored
            extra = row.extra_config or {}
            access_token_enc = extra.get("access_token_encrypted")
            if access_token_enc:
                access_token = decrypt(access_token_enc)
                kite_service.set_access_token(access_token)

            return True
        except Exception as e:
            logger.error(f"Failed to load Kite credentials from DB: {e}")
            return False


@router.get("/kite/login")
def kite_login():
    """
    Step 1 — Get Kite OAuth login URL.
    Frontend opens this URL in browser tab.
    After Kite login, user is redirected to /auth/kite/callback?request_token=...
    """
    if not _load_kite_credentials_from_db():
        raise HTTPException(
            status_code=400,
            detail="Zerodha API key/secret not configured. Go to Settings and save them first.",
        )
    try:
        login_url = kite_service.get_login_url()
        return {"login_url": login_url}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kite/callback")
def kite_callback(request_token: str = Query(...)):
    """
    Step 2 — OAuth callback. Kite redirects here after login.
    Exchange request_token for access_token and store encrypted.
    """
    try:
        access_token = kite_service.exchange_token(request_token)

        # Store access token encrypted in DB
        with SessionLocal() as db:
            row = db.query(ApiConfig).filter(
                ApiConfig.provider == "zerodha",
                ApiConfig.is_active == True,
            ).first()
            if row:
                extra = dict(row.extra_config or {})
                extra["access_token_encrypted"] = encrypt(access_token)
                row.extra_config = extra
                db.commit()
                logger.info("Kite access_token stored (encrypted) in DB")

        return {
            "status": "authenticated",
            "message": "Kite login successful. You can now start live market data.",
        }

    except Exception as e:
        logger.error(f"Kite OAuth callback failed: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/kite/status")
def kite_status():
    """Return current Kite connection status for the Settings UI."""
    return kite_service.get_status()


@router.post("/kite/validate")
def validate_kite_token():
    """Test if the stored access token is still valid (expires at ~6 AM each day)."""
    if not _load_kite_credentials_from_db():
        return {"valid": False, "message": "Kite credentials not configured"}
    valid = kite_service.validate_token()
    return {
        "valid": valid,
        "message": "Token valid ✅" if valid else "Token expired — please re-login to Kite",
    }


@router.post("/kite/start-feed")
async def start_live_feed():
    """
    Start KiteTicker WebSocket for live NIFTY market data.
    Call this after successful Kite login.
    Paper trade orders still simulated — only prices become real.
    """
    from app.core.strategy_engine import engine

    if not _load_kite_credentials_from_db():
        raise HTTPException(status_code=400, detail="Kite not configured")

    if not kite_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated — complete Kite OAuth login first",
        )

    if kite_service._ticker_running:
        return {"status": "already_running", "message": "Live feed already active"}

    try:
        loop = asyncio.get_event_loop()
        kite_service.start_ticker(
            on_nifty_tick=engine.on_nifty_tick,
            on_option_tick=engine.on_option_tick,
            loop=loop,
        )
        logger.info("Live NIFTY feed started via API request")
        return {
            "status": "started",
            "message": "Live NIFTY feed started. Strategy engine will use real prices.",
        }
    except Exception as e:
        logger.error(f"Failed to start live feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kite/stop-feed")
def stop_live_feed():
    """Stop KiteTicker (switch back to paper/mock mode)."""
    kite_service.stop_ticker()
    return {"status": "stopped", "message": "Live feed stopped"}


@router.post("/kite/load-instruments")
def load_instruments():
    """
    Manually trigger NFO instrument cache reload.
    Normally runs automatically at 9:00 AM.
    """
    if not kite_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")
    kite_service.load_instruments()
    return {
        "status": "loaded",
        "instruments_loaded": kite_service._instruments_loaded,
        "message": "NFO instrument cache refreshed",
    }


@router.post("/kite/logout")
def kite_logout():
    """Clear access token and stop live feed."""
    kite_service.clear_credentials()

    # Remove access token from DB
    with SessionLocal() as db:
        row = db.query(ApiConfig).filter(
            ApiConfig.provider == "zerodha",
            ApiConfig.is_active == True,
        ).first()
        if row:
            extra = dict(row.extra_config or {})
            extra.pop("access_token_encrypted", None)
            row.extra_config = extra
            db.commit()

    logger.info("Kite logged out — access token cleared")
    return {"status": "logged_out"}
