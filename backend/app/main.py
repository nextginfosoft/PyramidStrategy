"""
PyramidStrategy — FastAPI Application Entry Point
Multi-User refactored entry point.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.core.logging_config import setup_logging, update_logging_window

# Configure logger file sink for trade execution logs
setup_logging()

from app.config import settings
from app.db.database import init_db, get_redis_client
from app.api.routes import config, trades, strategy, auth, ai, session, notifications, backtest, analytics, admin
from app.api.websocket import websocket_endpoint
from app.core.engine_manager import engine_manager
from app.core.time_rules import today_ist


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def schedule_jobs():
    # 8:00 AM — token expiry validation + auto-login fallback
    async def token_check():
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        from app.services.kite_service import get_user_kite_service
        from app.services.encryption import decrypt, encrypt
        try:
            with SessionLocal() as db:
                configs = db.query(ApiConfig).filter(ApiConfig.provider == "zerodha", ApiConfig.is_active == True).all()
                for cfg in configs:
                    kite_serv = get_user_kite_service(cfg.user_id)
                    from app.api.routes.auth import _load_kite_credentials_from_db
                    _load_kite_credentials_from_db(cfg.user_id)
                    
                    is_valid = False
                    if kite_serv.is_authenticated():
                        is_valid = kite_serv.validate_token()
                    
                    if is_valid:
                        logger.info(f"✅ User {cfg.user_id}: Kite token valid at 8:00 AM check")
                    else:
                        logger.info(f"⏳ User {cfg.user_id}: Kite session invalid or expired. Attempting auto-login...")
                        extra = cfg.extra_config or {}
                        username = extra.get("username")
                        password_enc = extra.get("password_encrypted")
                        totp_secret_enc = extra.get("totp_secret_encrypted")
                        
                        if username and password_enc and totp_secret_enc:
                            try:
                                password = decrypt(password_enc)
                                totp_secret = decrypt(totp_secret_enc)
                                access_token = kite_serv.auto_login(username, password, totp_secret)
                                
                                # Store access token encrypted in DB
                                extra_updated = dict(cfg.extra_config or {})
                                extra_updated["access_token_encrypted"] = encrypt(access_token)
                                cfg.extra_config = extra_updated
                                db.commit()
                                logger.info(f"⚡ User {cfg.user_id}: Automated daily session validation & login successful!")
                            except Exception as autologin_ex:
                                logger.error(f"❌ User {cfg.user_id}: Automated login failed: {autologin_ex}")
                        else:
                            logger.warning(f"⚠️ User {cfg.user_id}: Automated login credentials not fully configured in settings.")
        except Exception as e:
            logger.warning(f"Scheduler token check job failed: {e}")

    scheduler.add_job(token_check, "cron", hour=8, minute=0, id="token_check")

    # 8:45 AM — pre-fetch daily AI gamification quotes
    async def ai_quotes_job():
        from app.gamification.ai_quotes import generate_daily_ai_quotes
        await generate_daily_ai_quotes(user_id=1)

    scheduler.add_job(ai_quotes_job, "cron", hour=8, minute=45, id="ai_quotes_job")

    # 9:00 AM — daily reset + reload NFO instruments
    async def daily_startup():
        from app.services.kite_service import get_user_kite_service
        # Reset all managed user engines
        for uid, eng in list(engine_manager._engines.items()):
            try:
                eng.daily_reset()
                kite_serv = get_user_kite_service(uid)
                if kite_serv.is_authenticated():
                    import asyncio
                    loop = asyncio.get_event_loop()
                    # Run instrument load in thread pool (blocking I/O)
                    await loop.run_in_executor(None, kite_serv.load_instruments)
                    logger.info(f"User {uid}: NFO instruments reloaded at 9:00 AM")
            except Exception as e:
                logger.error(f"Daily reset failed for User {uid}: {e}")

    scheduler.add_job(daily_startup, "cron", hour=9, minute=0, id="daily_reset")

    # 9:30 AM — pre-market brief job
    async def pre_market_brief_job():
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig
        from app.services.ai_service import run_pre_market_brief_for_user
        from app.core.time_rules import today_ist
        
        today = today_ist()
        logger.info(f"⏳ Running Pre-market AI Brief job at 9:30 AM for date: {today}")
        try:
            with SessionLocal() as db:
                configs = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).all()
                for cfg in configs:
                    await run_pre_market_brief_for_user(db, cfg.user_id, today)
        except Exception as e:
            logger.error(f"Scheduled pre-market brief job failed: {e}")

    scheduler.add_job(pre_market_brief_job, "cron", day_of_week="mon-fri", hour=9, minute=30, id="pre_market_brief")

    # Unified Minute-by-Minute Time Trigger Checker
    async def check_time_triggers():
        from app.db.database import SessionLocal
        from app.models.models import User, StrategyConfig
        from app.services.reporting import send_daily_report
        from app.core.time_rules import now_ist
        from datetime import date, timedelta
        
        now = now_ist()
        current_time_str = now.strftime("%H:%M")
        today = now.date()
        
        try:
            with SessionLocal() as db:
                users = db.query(User).all()
                for u in users:
                    # Get active strategy config
                    cfg = db.query(StrategyConfig).filter(
                        StrategyConfig.user_id == u.id, 
                        StrategyConfig.is_active == True
                    ).first()
                    
                    sq_time_str = "11:30"
                    if cfg and cfg.squareoff_time:
                        sq_time_str = cfg.squareoff_time
                        
                    try:
                        h, m = map(int, sq_time_str.split(":"))
                        sq_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                        
                        cutoff_dt = sq_dt - timedelta(minutes=15)
                        cutoff_time_str = cutoff_dt.strftime("%H:%M")
                        
                        report_dt = sq_dt + timedelta(minutes=15)
                        report_time_str = report_dt.strftime("%H:%M")
                        
                        # 1. Entry Cutoff Check
                        if current_time_str == cutoff_time_str:
                            logger.warning(f"🕐 {cutoff_time_str} — No more fresh entries allowed today for User {u.id}")
                            
                        # 2. Square-off Check
                        if current_time_str == sq_time_str:
                            eng = engine_manager._engines.get(u.id)
                            if eng and eng.is_running:
                                logger.warning(f"🔔 {sq_time_str} scheduler — triggering force squareoff for User {u.id}")
                                await eng._force_squareoff()
                                
                        # 3. Daily Report Check
                        if current_time_str == report_time_str:
                            logger.info(f"📊 {report_time_str} — Triggering automated EOD Daily Report for User {u.id}")
                            await send_daily_report(u.id, today)
                            try:
                                from app.services.ai_service import run_post_session_review_for_user
                                await run_post_session_review_for_user(db, u.id, today)
                            except Exception as ai_ex:
                                logger.error(f"Failed to trigger automated EOD AI post-session review: {ai_ex}")
                    except Exception as ex:
                        logger.error(f"Error parsing/triggering scheduler times for User {u.id}: {ex}")
        except Exception as e:
            logger.error(f"Error in unified time triggers check job: {e}")

    scheduler.add_job(check_time_triggers, "cron", minute="*", id="check_time_triggers")

    # Monday 9:00 AM — Weekly Summary Report
    async def weekly_reporting():
        from app.db.database import SessionLocal
        from app.models.models import User
        from app.services.reporting import send_weekly_report
        from datetime import date
        try:
            with SessionLocal() as db:
                users = db.query(User).all()
                for u in users:
                    await send_weekly_report(u.id, date.today())
        except Exception as e:
            logger.error(f"Weekly reporting job failed: {e}")

    scheduler.add_job(weekly_reporting, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_report")


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("PyramidStrategy Backend starting...")
    logger.info(f"  ENV: {settings.APP_ENV}")
    logger.info(f"  DB: {settings.DATABASE_URL}")
    logger.info(f"  Paper Trade: {settings.PAPER_TRADE}")
    logger.info(f"  Fake Redis: {settings.USE_FAKE_REDIS}")
    logger.info("=" * 60)

    # Init DB tables
    init_db()

    # Init Redis
    get_redis_client()

    # Schedule jobs
    schedule_jobs()
    scheduler.start()
    logger.info("Scheduler started")

    # Dynamic log window config update
    update_logging_window()

    # Load active strategy config into engines on startup
    _load_startup_config()

    # Restore Kite credentials and access token from DB
    _load_kite_on_startup()

    # Load AI observer configs from DB
    try:
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        from app.services.ai_service import get_user_ai_service
        with SessionLocal() as db:
            ai_configs = db.query(ApiConfig).filter(ApiConfig.provider.in_(["openai", "anthropic", "gemini"]), ApiConfig.is_active == True).all()
            for cfg in ai_configs:
                ai_serv = get_user_ai_service(cfg.user_id)
                ai_serv.load_from_db()

        # Pre-fetch daily AI motivational quotes on startup
        from app.gamification.ai_quotes import generate_daily_ai_quotes
        asyncio.create_task(generate_daily_ai_quotes(user_id=1))
    except Exception as e:
        logger.warning(f"AI service init failed (non-critical): {e}")

    # Load Telegram notification configs from DB
    try:
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        from app.services.notification import get_user_notification_service
        with SessionLocal() as db:
            telegram_configs = db.query(ApiConfig).filter(ApiConfig.provider == "telegram", ApiConfig.is_active == True).all()
            for cfg in telegram_configs:
                ns = get_user_notification_service(cfg.user_id)
                ns.load_from_db()
    except Exception as e:
        logger.warning(f"Notification service init failed (non-critical): {e}")

    # Start Telegram Bot Service polling
    try:
        from app.services.telegram_bot import telegram_bot_service
        await telegram_bot_service.start()
    except Exception as e:
        logger.warning(f"Telegram Bot service startup failed: {e}")

    yield

    # Shutdown
    try:
        from app.services.telegram_bot import telegram_bot_service
        await telegram_bot_service.stop()
    except Exception as e:
        pass
    scheduler.shutdown(wait=False)
    engine_manager.stop_all()
    logger.info("PyramidStrategy Backend stopped")


def _load_kite_on_startup():
    """
    Restore Kite API credentials and access token from DB for all users.
    If valid, start KiteTicker immediately so live data is ready at open.
    """
    from app.db.database import SessionLocal
    from app.models.models import ApiConfig
    from app.api.routes.auth import _load_kite_credentials_from_db
    from app.services.kite_service import get_user_kite_service

    try:
        with SessionLocal() as db:
            configs = db.query(ApiConfig).filter(ApiConfig.provider == "zerodha", ApiConfig.is_active == True).all()
            for cfg in configs:
                user_id = cfg.user_id
                configured = _load_kite_credentials_from_db(user_id)
                if not configured:
                    continue

                kite_service = get_user_kite_service(user_id)
                if kite_service.is_authenticated():
                    valid = kite_service.validate_token()
                    if valid:
                        logger.info(f"User {user_id}: Kite token valid on startup — starting live feed")
                        import asyncio
                        loop = asyncio.get_event_loop()
                        user_engine = engine_manager.get_engine(user_id)
                        kite_service.start_ticker(
                            on_nifty_tick=user_engine.on_nifty_tick,
                            on_option_tick=user_engine.on_option_tick,
                            loop=loop,
                        )
                        # Seed last closed NIFTY spot price if WebSocket is silent
                        try:
                            spot_price = kite_service.get_nifty_spot_ltp()
                            if spot_price:
                                asyncio.ensure_future(user_engine.on_nifty_tick(spot_price))
                                logger.info(f"User {user_id}: Seeded initial startup NIFTY price: {spot_price}")
                        except Exception as seed_err:
                            logger.warning(f"Failed to seed initial NIFTY price on startup: {seed_err}")
                        
                        # Load instruments in background (non-blocking)
                        asyncio.ensure_future(
                            loop.run_in_executor(None, kite_service.load_instruments)
                        )
                    else:
                        logger.warning(f"User {user_id}: Kite token expired on startup — re-login required")
    except Exception as e:
        logger.warning(f"Kite startup init failed (non-critical): {e}")


def _load_startup_config():
    """Load strategy config from DB into engine on startup."""
    from app.db.database import SessionLocal
    from app.models.models import StrategyConfig

    try:
        with SessionLocal() as db:
            configs = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).all()
            for cfg in configs:
                user_engine = engine_manager.get_engine(cfg.user_id)
                user_engine.load_config({
                    "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
                    "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
                    "lot_size": cfg.lot_size,
                    "target_points": float(cfg.target_points),
                    "sl_points": float(cfg.sl_points),
                    "paper_trade": cfg.paper_trade,
                })
                logger.info(f"User {cfg.user_id}: Strategy config loaded from DB on startup")
    except Exception as e:
        logger.warning(f"Could not load configs on startup: {e}")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PyramidStrategy API",
    description="Automated NIFTY Options Trading — Pyramid Strategy",
    version="1.1.8",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"❌ Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return await request_validation_exception_handler(request, exc)


# ── Routes ─────────────────────────────────────────────────────────────────────
# Without /api prefix
app.include_router(session.router)
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(trades.router)
app.include_router(strategy.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(backtest.router)
app.include_router(analytics.router)
app.include_router(admin.router)

# With /api prefix (supports direct requests to port 8000 using /api prefix, e.g. callback URLs)
app.include_router(session.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# ── Callback Route Aliases ───────────────────────────────────────────────────
# Redirect/callback targets configured in the Zerodha Developer Console vary.
# These aliases capture the request regardless of path (/callback, /api/callback, /auth/callback, etc.)
from app.api.routes.auth import kite_callback
from typing import Optional
from fastapi import Query

@app.get("/callback")
@app.get("/callback/")
@app.get("/api/callback")
@app.get("/api/callback/")
@app.get("/auth/callback")
@app.get("/auth/callback/")
@app.get("/api/auth/callback")
@app.get("/api/auth/callback/")
def root_kite_callback_alias(
    request_token: str = Query(...),
    user_id: Optional[int] = Query(None)
):
    return kite_callback(request_token=request_token, user_id=user_id)

# WebSocket
from fastapi import WebSocket
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/health")
def health():
    redis_ok = False
    try:
        r = get_redis_client()
        r.ping()
        redis_ok = True
    except Exception:
        pass

    active_engines_count = sum(1 for eng in engine_manager._engines.values() if eng.is_running)

    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "paper_trade": settings.PAPER_TRADE,
        "redis": "ok" if redis_ok else "error",
        "active_engines": active_engines_count,
        "total_managed_users": len(engine_manager._engines),
    }


# Serve static files for Frontend (single-server EXE setup)
import os
from fastapi.staticfiles import StaticFiles

current_dir = os.path.dirname(os.path.abspath(__file__))
# Check if frontend/dist exists in the package internal structure, or in local development
frontend_dist = os.path.abspath(os.path.join(current_dir, "frontend", "dist"))
if not os.path.exists(frontend_dist):
    # Try dev path relative to app folder
    frontend_dist = os.path.abspath(os.path.join(current_dir, "..", "..", "frontend", "dist"))

if os.path.exists(frontend_dist):
    logger.info(f"Mounting static files from: {frontend_dist}")
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    logger.warning(f"Frontend dist folder not found at: {frontend_dist}")


if __name__ == "__main__":
    import uvicorn
    import uvicorn.logging
    import webbrowser
    import threading
    import time

    def open_browser():
        # Wait a moment for uvicorn to start serving requests
        time.sleep(1.5)
        url = "http://127.0.0.1:8000"
        logger.info(f"Opening default web browser to {url}...")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"Failed to open web browser: {e}")

    # Start browser opener in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    logger.info("Starting uvicorn server on http://127.0.0.1:8000")
    try:
        # Run the server with log_config=None to avoid PyInstaller dictConfig formatter errors
        uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
    except Exception as e:
        logger.error(f"Uvicorn server failed to start: {e}")
