import datetime
from loguru import logger

# Shared logging window variables (in IST)
log_end_hour = 12
log_end_minute = 30
_logging_setup = False

def log_time_filter(record):
    try:
        ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        t = datetime.datetime.now(ist_tz).time()
        return datetime.time(9, 0) <= t <= datetime.time(log_end_hour, log_end_minute)
    except Exception:
        # Fallback to true on unexpected errors
        return True

def setup_logging():
    global _logging_setup
    if _logging_setup:
        return
    logger.add(
        "trade_engine.log",
        rotation="10 MB",
        retention="10 days",
        level="INFO",
        enqueue=True,
        filter=log_time_filter
    )
    _logging_setup = True

def update_logging_window():
    """Dynamically scan active StrategyConfigs to extend log window up to squareoff_time + 1.5 hours."""
    try:
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig
        global log_end_hour, log_end_minute
        with SessionLocal() as db:
            configs = db.query(StrategyConfig).filter(StrategyConfig.is_active == True).all()
            max_minutes = 12 * 60 + 30  # Default 12:30 PM
            for cfg in configs:
                if cfg.squareoff_time:
                    try:
                        h, m = map(int, cfg.squareoff_time.split(":"))
                        # Extend logging by 1.5 hours (90 mins) to capture force squareoff + EOD reports
                        total_mins = h * 60 + m + 90
                        if total_mins > max_minutes:
                            max_minutes = total_mins
                    except Exception:
                        pass
            
            # Bound it to a maximum of 23:59
            max_minutes = min(max_minutes, 23 * 60 + 59)
            
            log_end_hour = max_minutes // 60
            log_end_minute = max_minutes % 60
            logger.info(f"🔄 Logging window extended to {log_end_hour:02d}:{log_end_minute:02d} IST based on active configurations.")
    except Exception as e:
        logger.error(f"Error dynamically updating logging window: {e}")
