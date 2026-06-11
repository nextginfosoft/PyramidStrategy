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
from app.api.routes import config, trades, strategy
from app.api.websocket import websocket_endpoint
from app.core.strategy_engine import engine
from app.core.time_rules import today_ist


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def schedule_jobs():
    # 9:00 AM — daily reset
    scheduler.add_job(engine.daily_reset, "cron", hour=9, minute=0, id="daily_reset")

    # 11:15 AM — log warning, entries blocked
    scheduler.add_job(
        lambda: logger.warning("🕐 11:15 AM — No more fresh entries allowed today"),
        "cron", hour=11, minute=15, id="entry_cutoff_log"
    )

    # 11:30 AM — force squareoff (engine handles this on each tick too)
    async def scheduled_squareoff():
        from app.core.strategy_engine import engine as eng
        import asyncio
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

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("PyramidStrategy Backend stopped")


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
app.include_router(config.router)
app.include_router(trades.router)
app.include_router(strategy.router)

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

    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "paper_trade": settings.PAPER_TRADE,
        "redis": "ok" if redis_ok else "error",
        "engine_running": engine.is_running,
    }
