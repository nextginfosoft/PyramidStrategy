from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StrategyConfig(Base):
    __tablename__ = "strategy_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    r1 = Column(Numeric(10, 2), nullable=False)
    r2 = Column(Numeric(10, 2), nullable=False)
    r3 = Column(Numeric(10, 2), nullable=False)
    s1 = Column(Numeric(10, 2), nullable=False)
    s2 = Column(Numeric(10, 2), nullable=False)
    s3 = Column(Numeric(10, 2), nullable=False)
    lot_size = Column(Integer, default=75)       # NIFTY lot size
    target_points = Column(Numeric(6, 2), default=20)
    sl_points = Column(Numeric(6, 2), default=10)
    paper_trade = Column(Boolean, default=True)
    squareoff_time = Column(String(5), default="11:30")
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    post_exit_high = Column(Numeric(10, 2))
    post_exit_high_time = Column(DateTime(timezone=True))
    post_exit_low = Column(Numeric(10, 2))
    post_exit_low_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DailyPnL(Base):
    __tablename__ = "daily_pnl"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trade_date = Column(Date, nullable=False, index=True)
    gross_pnl = Column(Numeric(12, 2), default=0)
    brokerage = Column(Numeric(12, 2), default=0)
    net_pnl = Column(Numeric(12, 2), default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    ce_pnl = Column(Numeric(12, 2), default=0)
    pe_pnl = Column(Numeric(12, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "trade_date", name="uq_user_trade_date"),
    )


class ApiConfig(Base):
    __tablename__ = "api_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(30), nullable=False)  # zerodha/openai/anthropic/telegram
    api_key_encrypted = Column(Text)
    api_secret_encrypted = Column(Text)
    extra_config = Column(JSON)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
    )


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trade_date = Column(Date, nullable=False, index=True)
    event = Column(String(20), nullable=False)      # ENTRY / EXIT / SL / SQUAREOFF
    side = Column(String(2))                         # CE / PE
    level = Column(String(10))
    nifty_ltp = Column(Numeric(10, 2))
    provider = Column(String(20))                    # openai / anthropic / gemini
    suggestion = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)   # LEVEL_TRIGGERED/ORDER_PLACED/TARGET_HIT/etc
    side = Column(String(2))
    level = Column(String(2))
    nifty_price = Column(Numeric(10, 2))
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PreMarketBrief(Base):
    __tablename__ = "pre_market_briefs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trade_date = Column(Date, nullable=False, index=True)
    vix = Column(Numeric(10, 2))
    vix_analysis = Column(Text)
    expected_range = Column(Text)
    level_assessment = Column(Text)
    suggested_config = Column(JSON)  # {"s1": float, "s2": float, ..., "recommended_lots": int}
    quality_score = Column(Integer)
    quality_reason = Column(Text)
    pcr = Column(Numeric(6, 2))
    max_pain = Column(Numeric(10, 2))
    ce_wall = Column(Numeric(10, 2))
    pe_wall = Column(Numeric(10, 2))
    opening_gap = Column(Numeric(10, 2))
    approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "trade_date", name="uq_user_premarket_trade_date"),
    )
