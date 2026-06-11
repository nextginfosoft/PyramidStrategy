from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


# ── Strategy Config ───────────────────────────────────────────────────────────
class StrategyConfigBase(BaseModel):
    r1: Decimal
    r2: Decimal
    r3: Decimal
    s1: Decimal
    s2: Decimal
    s3: Decimal
    lot_size: int = 75
    target_points: Decimal = Decimal("20")
    sl_points: Decimal = Decimal("10")

    @model_validator(mode="after")
    def validate_levels(self):
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
    avg_price: Optional[Decimal]
    trigger_nifty_level: Optional[Decimal]
    kite_order_id: Optional[str]
    status: str
    pnl: Optional[Decimal]
    is_paper_trade: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Daily P&L ─────────────────────────────────────────────────────────────────
class DailyPnLResponse(BaseModel):
    trade_date: date
    gross_pnl: Decimal
    net_pnl: Decimal
    total_trades: int
    winning_trades: int
    ce_pnl: Decimal
    pe_pnl: Decimal

    model_config = {"from_attributes": True}


# ── Strategy Status (live state — not from DB) ────────────────────────────────
class SideStatus(BaseModel):
    state: str                        # IDLE / L1_ENTERED / L2_ENTERED / L3_ENTERED / BLOCKED
    lots: int = 0
    locked_strike: Optional[int] = None
    locked_instrument: Optional[str] = None
    entry_avg_price: Optional[Decimal] = None
    current_ltp: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    blocked_levels: list[str] = []


class StrategyStatus(BaseModel):
    is_running: bool
    paper_trade: bool
    nifty_ltp: Optional[Decimal]
    ce: SideStatus
    pe: SideStatus
    today_pnl: Decimal = Decimal("0")
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

    model_config = {"from_attributes": True}


# ── WebSocket Messages ────────────────────────────────────────────────────────
class WSMessage(BaseModel):
    type: str   # nifty_tick | trade_event | strategy_status | ai_suggestion | error
    data: dict
    timestamp: datetime = datetime.now()
