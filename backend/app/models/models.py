from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.database import Base


class StrategyConfig(Base):
    __tablename__ = "strategy_config"

    id = Column(Integer, primary_key=True, index=True)
    r1 = Column(Numeric(10, 2), nullable=False)
    r2 = Column(Numeric(10, 2), nullable=False)
    r3 = Column(Numeric(10, 2), nullable=False)
    s1 = Column(Numeric(10, 2), nullable=False)
    s2 = Column(Numeric(10, 2), nullable=False)
    s3 = Column(Numeric(10, 2), nullable=False)
    lot_size = Column(Integer, default=75)       # NIFTY lot size
    target_points = Column(Numeric(6, 2), default=20)
    sl_points = Column(Numeric(6, 2), default=10)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    side = Column(String(2), nullable=False)          # CE or PE
    level = Column(String(2), nullable=False)          # R1,R2,R3,S1,S2,S3
    instrument = Column(String(50), nullable=False)    # NIFTY11JUN2524150PE
    strike = Column(Integer, nullable=False)
    expiry = Column(Date, nullable=False)
    action = Column(String(4), nullable=False)         # BUY or EXIT
    lots = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)              # lots × lot_size
    avg_price = Column(Numeric(10, 2))
    trigger_nifty_level = Column(Numeric(10, 2))
    kite_order_id = Column(String(50))
    status = Column(String(20), default="OPEN")        # OPEN/TARGET/SL/SQUAREOFF/CANCELLED
    pnl = Column(Numeric(12, 2))
    is_paper_trade = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DailyPnL(Base):
    __tablename__ = "daily_pnl"

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, unique=True, nullable=False, index=True)
    gross_pnl = Column(Numeric(12, 2), default=0)
    brokerage = Column(Numeric(12, 2), default=0)
    net_pnl = Column(Numeric(12, 2), default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    ce_pnl = Column(Numeric(12, 2), default=0)
    pe_pnl = Column(Numeric(12, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiConfig(Base):
    __tablename__ = "api_config"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(30), nullable=False, unique=True)  # zerodha/openai/anthropic/telegram
    api_key_encrypted = Column(Text)
    api_secret_encrypted = Column(Text)
    extra_config = Column(JSON)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)   # LEVEL_TRIGGERED/ORDER_PLACED/TARGET_HIT/etc
    side = Column(String(2))
    level = Column(String(2))
    nifty_price = Column(Numeric(10, 2))
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
