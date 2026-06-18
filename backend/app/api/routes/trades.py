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


@router.get("/export")
def export_trades(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse

    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id)
        .order_by(Trade.created_at.asc())
        .all()
    )

    entries = [t for t in trades if t.action == "BUY"]
    exits = [t for t in trades if t.action == "EXIT"]

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Trade ID", "Trigger Level", "Instrument", "Strike", "Expiry", 
        "Lots", "Quantity", "Entry Timing", "Entry Price", "Entry Nifty", 
        "Exit Timing", "Exit Price", "Exit Nifty", "Exit Reason", 
        "PnL (Rupees)", "Is Paper Trade"
    ])

    for entry in entries:
        # Map Level (L1, L2, L3) to R1/R2/R3 or S1/S2/S3
        lvl = entry.level
        if entry.side == "PE":
            if lvl == "L1": strategy_level = "R1"
            elif lvl == "L2": strategy_level = "R2"
            elif lvl == "L3": strategy_level = "R3"
            else: strategy_level = lvl
        elif entry.side == "CE":
            if lvl == "L1": strategy_level = "S1"
            elif lvl == "L2": strategy_level = "S2"
            elif lvl == "L3": strategy_level = "S3"
            else: strategy_level = lvl
        else:
            strategy_level = lvl

        # Find corresponding exit
        matching_exit = None
        for ext in exits:
            if ext.instrument == entry.instrument and ext.created_at > entry.created_at:
                matching_exit = ext
                break

        if matching_exit:
            exit_time_str = matching_exit.created_at.isoformat()
            exit_price_val = float(matching_exit.avg_price) if matching_exit.avg_price is not None else ""
            exit_nifty_val = float(matching_exit.trigger_nifty_level) if matching_exit.trigger_nifty_level is not None else ""
            exit_reason_str = matching_exit.status
            pnl_val = float((matching_exit.avg_price - entry.avg_price) * entry.qty) if matching_exit.avg_price is not None and entry.avg_price is not None else ""
        else:
            exit_time_str = "OPEN"
            exit_price_val = ""
            exit_nifty_val = ""
            exit_reason_str = "OPEN"
            pnl_val = ""

        writer.writerow([
            entry.id,
            strategy_level,
            entry.instrument,
            entry.strike,
            entry.expiry.isoformat() if entry.expiry else "",
            entry.lots,
            entry.qty,
            entry.created_at.isoformat() if entry.created_at else "",
            float(entry.avg_price) if entry.avg_price is not None else "",
            float(entry.trigger_nifty_level) if entry.trigger_nifty_level is not None else "",
            exit_time_str,
            exit_price_val,
            exit_nifty_val,
            exit_reason_str,
            pnl_val,
            entry.is_paper_trade
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pyramid_trades.csv"}
    )


@router.get("/logs")
def get_logs(
    start_time: str = Query(default="09:00", description="HH:MM format"),
    end_time: str = Query(default="12:30", description="HH:MM format"),
    user: User = Depends(require_auth)
):
    import os
    import re
    from datetime import time
    from fastapi import HTTPException

    log_path = "trade_engine.log"
    if not os.path.exists(log_path):
        return {"logs": []}

    try:
        sh, sm = map(int, start_time.split(":"))
        t_start = time(sh, sm)
        eh, em = map(int, end_time.split(":"))
        t_end = time(eh, em)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_time or end_time format. Use HH:MM")

    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2}):(\d{2})")

    filtered_lines = []
    include_line = False

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.match(line)
            if match:
                _, hour, minute, second = match.groups()
                log_time = time(int(hour), int(minute), int(second))
                include_line = t_start <= log_time <= t_end

            if include_line:
                filtered_lines.append(line.rstrip("\n"))

    return {"logs": filtered_lines}


@router.get("/logs/export")
def export_logs(user: User = Depends(require_auth)):
    import os
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    log_path = "trade_engine.log"
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Log file not found. Check if engine has started.")
    
    return FileResponse(
        path=log_path,
        media_type="text/plain",
        filename="trade_engine.log"
    )
