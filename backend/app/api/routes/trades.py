from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date
from app.db.database import get_db
from app.models.models import Trade, DailyPnL, User
from app.schemas.schemas import TradeResponse, DailyPnLResponse
from app.core.time_rules import today_ist
from app.api.routes.session import require_auth

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/today", response_model=list[TradeResponse])
def get_today_trades(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.trade_date == today_ist())
        .order_by(desc(Trade.created_at))
        .all()
    )
    return trades


@router.get("/history", response_model=list[TradeResponse])
def get_trade_history(
    from_date: date | None = None,
    to_date: date | None = None,
    side: str | None = Query(default=None, pattern="^(CE|PE)$"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    q = db.query(Trade).filter(Trade.user_id == user.id)
    if from_date:
        q = q.filter(Trade.trade_date >= from_date)
    if to_date:
        q = q.filter(Trade.trade_date <= to_date)
    if side:
        q = q.filter(Trade.side == side)
    return q.order_by(desc(Trade.created_at)).limit(limit).all()


@router.get("/pnl/today")
def get_today_pnl(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    trades = (
        db.query(Trade)
        .filter(
            Trade.user_id == user.id,
            Trade.trade_date == today_ist(),
            Trade.action == "EXIT"
        )
        .all()
    )
    total_pnl = sum((float(t.pnl or 0) for t in trades), 0.0)
    winning = sum(1 for t in trades if (t.pnl or 0) > 0)
    return {
        "trade_date": today_ist().isoformat(),
        "gross_pnl": round(total_pnl, 2),
        "total_exits": len(trades),
        "winning_trades": winning,
        "losing_trades": len(trades) - winning,
    }


@router.get("/pnl/history", response_model=list[DailyPnLResponse])
def get_pnl_history(
    limit: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    return (
        db.query(DailyPnL)
        .filter(DailyPnL.user_id == user.id)
        .order_by(desc(DailyPnL.trade_date))
        .limit(limit)
        .all()
    )
