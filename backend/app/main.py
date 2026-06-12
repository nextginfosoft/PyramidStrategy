"""
PyramidStrategy — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import settings
from app.db.database import init_db, get_redis_client
from app.api.routes import config, trades, strategy, auth, ai, session, notifications
from app.api.websocket import websocket_endpoint
from app.core.strategy_engine import engine
from app.core.time_rules import today_ist


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def schedule_jobs():
    # 8:00 AM — token expiry reminder + auto-validate Kite token
    async def token_check():
        from app.services.kite_service import kite_service
        if kite_service.is_authenticated():
            valid = kite_service.validate_token()
            if not valid:
                logger.warning("⚠️  Kite access token EXPIRED — re-login required before trading")
            else:
                logger.info("✅ Kite token valid at 8:00 AM check")
        else:
            logger.info("ℹ️  Kite not connected at 8:00 AM — skipping token check")

    scheduler.add_job(token_check, "cron", hour=8, minute=0, id="token_check")

    # 9:00 AM — daily reset + reload NFO instruments
    async def daily_startup():
        engine.daily_reset()
        from app.services.kite_service import kite_service
        if kite_service.is_authenticated():
            import asyncio
            # Run instrument load in thread pool (blocking I/O)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, kite_service.load_instruments)
            logger.info("NFO instruments reloaded at 9:00 AM")

    scheduler.add_job(daily_startup, "cron", hour=9, minute=0, id="daily_reset")

    # 11:15 AM — log warning, entries blocked
    scheduler.add_job(
        lambda: logger.warning("🕐 11:15 AM — No more fresh entries allowed today"),
        "cron", hour=11, minute=15, id="entry_cutoff_log"
    )

    # 11:30 AM — force squareoff
    async def scheduled_squareoff():
        from app.core.strategy_engine import engine as eng
        if eng.is_running:
            logger.warning("🔔 11:30 AM scheduler — triggering force squareoff")
            await eng._force_squareoff()

    scheduler.add_job(scheduled_squareoff, "cron", hour=11, minute=30, id="squareoff")


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

    # Load active strategy config into engine on startup
    _load_startup_config()

    # Restore Kite credentials and access token from DB
    _load_kite_on_startup()

    # Load AI observer config from DB
    try:
        from app.services.ai_service import ai_service
        ai_service.load_from_db()
        logger.info(f"AI service: enabled={ai_service.is_enabled()}, provider={ai_service._provider}")
    except Exception as e:
        logger.warning(f"AI service init failed (non-critical): {e}")

    # Load Telegram notification config from DB
    try:
        from app.services.notification import notification_service
        notification_service.load_from_db()
        logger.info(f"Telegram notifications: enabled={notification_service.is_enabled()}")
    except Exception as e:
        logger.warning(f"Notification service init failed (non-critical): {e}")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("PyramidStrategy Backend stopped")


def _load_kite_on_startup():
    """
    Restore Kite API credentials and access token from DB.
    If valid, start KiteTicker immediately so live data is ready at open.
    """
    from app.api.routes.auth import _load_kite_credentials_from_db
    from app.services.kite_service import kite_service

    try:
        configured = _load_kite_credentials_from_db()
        if not configured:
            logger.info("Kite credentials not configured — running in mock mode")
            return

        if kite_service.is_authenticated():
            valid = kite_service.validate_token()
            if valid:
                logger.info("Kite token valid on startup — starting live feed")
                import asyncio
                loop = asyncio.get_event_loop()
                kite_service.start_ticker(
                    on_nifty_tick=engine.on_nifty_tick,
                    on_option_tick=engine.on_option_tick,
                    loop=loop,
                )
                # Load instruments in background (non-blocking)
                asyncio.ensure_future(
                    loop.run_in_executor(None, kite_service.load_instruments)
                )
            else:
                logger.warning("Kite token expired on startup — re-login required")
    except Exception as e:
        logger.warning(f"Kite startup init failed (non-critical): {e}")


def _load_startup_config():
    """Load strategy config from DB into engine on startup."""
    from app.db.database import SessionLocal
    from app.models.models import StrategyConfig

    try:
        with SessionLocal() as db:
            cfg = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).first()
            if cfg:
                engine.load_config({
                    "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
                    "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
                    "lot_size": cfg.lot_size,
                    "target_points": float(cfg.target_points),
                    "sl_points": float(cfg.sl_points),
                })
                logger.info("Strategy config loaded from DB on startup")
    except Exception as e:
        logger.warning(f"Could not load config on startup: {e}")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PyramidStrategy API",
    description="Automated NIFTY Options Trading — Pyramid Strategy",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(session.router)
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(trades.router)
app.include_router(strategy.router)
app.include_router(ai.router)
app.include_router(notifications.router)

# WebSocket
from fastapi import WebSocket
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/health")
def health():
    from app.services.kite_service import kite_service
    from app.services.ai_service import ai_service
    from app.services.notification import notification_service
    redis_ok = False
    try:
        r = get_redis_client()
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "paper_trade": settings.PAPER_TRADE,
        "redis": "ok" if redis_ok else "error",
        "engine_running": engine.is_running,
        "kite": {
            "authenticated": kite_service.is_authenticated(),
            "ticker_connected": kite_service._is_connected,
            "instruments_loaded": kite_service._instruments_loaded,
        },
        "ai": {
            "enabled": ai_service.is_enabled(),
            "provider": ai_service._provider,
        },
        "telegram": {
            "enabled": notification_service.is_enabled(),
        },
    }
