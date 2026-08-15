from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from app.config import settings
from loguru import logger


# ── Engine setup ──────────────────────────────────────────────────────────────
import sys
import os

db_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL

if settings.is_sqlite and ":memory:" not in db_url:
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen and os.environ.get("APPDATA"):
        app_data_dir = os.path.join(os.environ["APPDATA"], "PyramidStrategy")
        os.makedirs(app_data_dir, exist_ok=True)
        db_path = os.path.join(app_data_dir, "pyramidstrategy.db")
        db_url = f"sqlite:///{db_path}"
        logger.info(f"Packaged executable detected. SQLite database relocated to: {db_path}")
    elif db_url.startswith("sqlite:///./"):
        # Resolve relative SQLite path to root project directory for consistency
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(root_dir, "pyramidstrategy.db")
        db_url = f"sqlite:///{db_path}"

if settings.is_sqlite:
    if ":memory:" in db_url:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
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
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 10},
    )

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
    
    # Self-healing migration for users table
    for col, col_type in [
        ("is_approved", "BOOLEAN DEFAULT FALSE NOT NULL"),
        ("is_admin", "BOOLEAN DEFAULT FALSE NOT NULL")
    ]:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Database migration: Added {col} to users")
        except Exception as e:
            # Expected error if column already exists
            logger.debug(f"Database migration (users.{col} check/add): {e}")
    
    # Auto-approve and promote SUPER_ADMIN_USERNAME if they exist
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE users SET is_approved = TRUE, is_admin = TRUE WHERE username = :username"
            ), {"username": settings.SUPER_ADMIN_USERNAME})
            conn.commit()
            logger.info(f"Database migration: Auto-promoted super admin user '{settings.SUPER_ADMIN_USERNAME}'")
    except Exception as e:
        logger.warning(f"Failed to auto-promote super admin: {e}")
    
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

    # Self-healing migration for strategy_type
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE strategy_config ADD COLUMN strategy_type VARCHAR(50) DEFAULT 'PYRAMID'"))
            conn.commit()
            logger.info("Database migration: Added strategy_type to strategy_config")
    except Exception as e:
        logger.debug(f"Database migration (strategy_type check/add): {e}")

    # Self-healing migration for users email and google_id
    for col, col_type in [("email", "VARCHAR(255)"), ("google_id", "VARCHAR(255)")]:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"Database migration: Added {col} to users")
        except Exception as e:
            logger.debug(f"Database migration (users.{col} check/add): {e}")

    # Self-healing migration for trades columns
    for col, col_type in [
        ("active_high", "NUMERIC(10, 2)"),
        ("active_high_time", "TIMESTAMP"),
        ("active_low", "NUMERIC(10, 2)"),
        ("active_low_time", "TIMESTAMP"),
        ("post_exit_high", "NUMERIC(10, 2)"),
        ("post_exit_high_time", "TIMESTAMP"),
        ("post_exit_low", "NUMERIC(10, 2)"),
        ("post_exit_low_time", "TIMESTAMP"),
        ("price_at_320", "NUMERIC(10, 2)")
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

    # Self-healing migration to increase trades.level column length to VARCHAR(10)
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE trades ALTER COLUMN level TYPE VARCHAR(10)"))
            conn.commit()
            logger.info("Database migration: Altered trades.level type to VARCHAR(10)")
    except Exception as e:
        logger.warning(f"Database migration (alter trades.level type): {e}")
