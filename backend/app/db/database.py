from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from app.config import settings
from loguru import logger


# ── Engine setup ──────────────────────────────────────────────────────────────
if settings.is_sqlite:
    if ":memory:" in settings.DATABASE_URL:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
        
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception as e:
            logger.debug(f"Failed to set sqlite pragma WAL: {e}")
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── Redis setup ───────────────────────────────────────────────────────────────
def get_redis():
    if settings.USE_FAKE_REDIS:
        import fakeredis
        return fakeredis.FakeRedis(decode_responses=True)
    else:
        import redis
        return redis.from_url(settings.REDIS_URL, decode_responses=True)


# Singleton redis client
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = get_redis()
        logger.info(f"Redis initialized ({'fakeredis' if settings.USE_FAKE_REDIS else settings.REDIS_URL})")
    return _redis_client


# ── DB dependency (FastAPI) ───────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup."""
    from app.models import models  # noqa: F401 — import to register models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    # Self-healing migration for squareoff_time
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE strategy_config ADD COLUMN squareoff_time VARCHAR(5) DEFAULT '11:30'"))
            conn.commit()
            logger.info("Database migration: Added squareoff_time to strategy_config")
    except Exception as e:
        # Expected error if column already exists
        logger.debug(f"Database migration (squareoff_time check/add): {e}")

    # Self-healing migration for post_exit columns
    for col, col_type in [
        ("post_exit_high", "NUMERIC(10, 2)"),
        ("post_exit_high_time", "TIMESTAMP"),
        ("post_exit_low", "NUMERIC(10, 2)"),
        ("post_exit_low_time", "TIMESTAMP")
    ]:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE trades ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Database migration: Added {col} to trades")
        except Exception as e:
            # Expected error if column already exists
            logger.debug(f"Database migration (trades.{col} check/add): {e}")
