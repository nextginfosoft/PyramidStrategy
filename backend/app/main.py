"""
PyramidStrategy — FastAPI Application Entry Point
Multi-User refactored entry point.
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
from app.core.engine_manager import engine_manager
from app.core.time_rules import today_ist


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def schedule_jobs():
    # 8:00 AM — token expiry reminder + auto-validate Kite token
    async def token_check():
        from app.db.database import SessionLocal
        from app.models.models import ApiConfig
        from app.services.kite_service import get_user_kite_service
        try:
            with SessionLocal() as db:
                configs = db.query(ApiConfig).filter(ApiConfig.provider == "zerodha", ApiConfig.is_active == True).all()
                for cfg in configs:
                    kite_serv = get_user_kite_service(cfg.user_id)
                    if kite_serv.is_authenticated():
                        valid = kite_serv.validate_token()
                        if not valid:
                            logger.warning(f"⚠️ User {cfg.user_id}: Kite access token EXPIRED — re-login required")
                        else:
                            logger.info(f"✅ User {cfg.user_id}: Kite token valid at 8:00 AM check")
        except Exception as e:
            logger.warning(f"Scheduler token check job failed: {e}")

    scheduler.add_job(token_check, "cron", hour=8, minute=0, id="token_check")

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

    # 11:15 AM — log warning, entries blocked
    scheduler.add_job(
        lambda: logger.warning("🕐 11:15 AM — No more fresh entries allowed today"),
        "cron", hour=11, minute=15, id="entry_cutoff_log"
    )

    # 11:30 AM — force squareoff
    async def scheduled_squareoff():
        for uid, eng in list(engine_manager._engines.items()):
            if eng.is_running:
                try:
                    logger.warning(f"🔔 11:30 AM scheduler — triggering force squareoff for User {uid}")
                    await eng._force_squareoff()
                except Exception as e:
                    logger.error(f"Scheduled squareoff failed for User {uid}: {e}")

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

    yield

    # Shutdown
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
                })
                logger.info(f"User {cfg.user_id}: Strategy config loaded from DB on startup")
    except Exception as e:
        logger.warning(f"Could not load configs on startup: {e}")


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
