from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import date, datetime, timezone
from decimal import Decimal


# ── Strategy Config ───────────────────────────────────────────────────────────
class StrategyConfigBase(BaseModel):
    r1: float
    r2: Optional[float] = 0.0
    r3: Optional[float] = 0.0
    s1: float
    s2: Optional[float] = 0.0
    s3: Optional[float] = 0.0
    lot_size: int = 65
    target_points: float = 30.0
    sl_points: float = 10.0
    paper_trade: bool = True
    squareoff_time: str = "15:20"
    strategy_type: str = "PYRAMID"

    @field_validator("squareoff_time")
    @classmethod
    def validate_squareoff_time(cls, v):
        try:
            h, m = map(int, v.split(":"))
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError("Invalid time format")
            minutes = h * 60 + m
            min_bound = 9 * 60 + 30  # 09:30 AM
            max_bound = 15 * 60 + 30  # 03:30 PM
            if not (min_bound <= minutes <= max_bound):
                raise ValueError("Square-off time must be between 09:30 AM and 03:30 PM")
        except Exception as e:
            if "must be between" in str(e):
                raise ValueError(str(e))
            raise ValueError("Square-off time must be in HH:MM format between 09:30 and 15:30")
        return v

    @model_validator(mode="after")
    def validate_levels(self):
        if self.strategy_type == "PYRAMID":
            # PE levels must be ascending
            if not (self.r1 < self.r2 < self.r3):
                raise ValueError("Resistance levels must be ascending: R1 < R2 < R3")
            # CE levels must be descending
            if not (self.s1 > self.s2 > self.s3):
                raise ValueError("Support levels must be descending: S1 > S2 > S3")
        return self


class StrategyConfigCreate(StrategyConfigBase):
    pass


class StrategyConfigResponse(StrategyConfigBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Trade ─────────────────────────────────────────────────────────────────────
class TradeResponse(BaseModel):
    id: int
    trade_date: date
    side: str
    level: str
    instrument: str
    strike: int
    expiry: date
    action: str
    lots: int
    qty: int
    avg_price: Optional[float]
    trigger_nifty_level: Optional[float]
    kite_order_id: Optional[str]
    status: str
    pnl: Optional[float]
    is_paper_trade: bool
    active_high: Optional[float] = None
    active_high_time: Optional[datetime] = None
    active_low: Optional[float] = None
    active_low_time: Optional[datetime] = None
    post_exit_high: Optional[float] = None
    post_exit_high_time: Optional[datetime] = None
    post_exit_low: Optional[float] = None
    post_exit_low_time: Optional[datetime] = None
    price_at_320: Optional[float] = None
    created_at: datetime

    @field_validator("created_at", "active_high_time", "active_low_time", "post_exit_high_time", "post_exit_low_time", mode="before")
    @classmethod
    def ensure_tz(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
        elif isinstance(v, str):
            try:
                # Handle ISO format strings if passed directly
                from dateutil.parser import parse
                dt = parse(v)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
        return v

    model_config = {"from_attributes": True}


# ── Daily P&L ─────────────────────────────────────────────────────────────────
class DailyPnLResponse(BaseModel):
    trade_date: date
    gross_pnl: float
    net_pnl: float
    total_trades: int
    winning_trades: int
    ce_pnl: float
    pe_pnl: float

    model_config = {"from_attributes": True}


# ── Strategy Status (live state — not from DB) ────────────────────────────────
class SideStatus(BaseModel):
    state: str                        # IDLE / L1_ENTERED / L2_ENTERED / L3_ENTERED / BLOCKED
    lots: int = 0
    locked_strike: Optional[int] = None
    locked_instrument: Optional[str] = None
    entry_avg_price: Optional[float] = None
    current_ltp: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    blocked_levels: list[str] = []


class StrategyStatus(BaseModel):
    is_running: bool
    paper_trade: bool
    nifty_ltp: Optional[float]
    nifty_prev_close: Optional[float] = None
    ce: SideStatus
    pe: SideStatus
    today_pnl: float = 0.0
    entries_allowed: bool             # False after 11:15 AM
    squareoff_triggered: bool         # True at/after 11:30 AM



# ── API Config (Settings UI) ──────────────────────────────────────────────────
class ApiConfigUpdate(BaseModel):
    provider: str
    api_key: Optional[str] = None     # plaintext from frontend, encrypted in backend
    api_secret: Optional[str] = None
    extra_config: Optional[dict] = None


class ApiConfigResponse(BaseModel):
    provider: str
    api_key_masked: Optional[str]     # e.g. "sk-...xxxx"
    is_active: bool
    extra_config: Optional[dict] = None

    model_config = {"from_attributes": True}


# ── WebSocket Messages ────────────────────────────────────────────────────────
class WSMessage(BaseModel):
    type: str   # nifty_tick | trade_event | strategy_status | ai_suggestion | error
    data: dict
    timestamp: datetime = datetime.now()
