from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime
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
def export_trades(period: str = "all", db: Session = Depends(get_db), user: User = Depends(require_auth)):
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse
    import pytz
    from datetime import datetime, timedelta

    query = db.query(Trade).filter(Trade.user_id == user.id)

    if period != "all":
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Trade.created_at >= start_date.astimezone(pytz.utc))
        elif period == "weekly":
            start_date = now - timedelta(days=7)
            query = query.filter(Trade.created_at >= start_date.astimezone(pytz.utc))
        elif period == "monthly":
            start_date = now - timedelta(days=30)
            query = query.filter(Trade.created_at >= start_date.astimezone(pytz.utc))

    trades = query.order_by(Trade.created_at.asc()).all()

    entries = [t for t in trades if t.action == "BUY"]
    exits = [t for t in trades if t.action == "EXIT"]

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Trade ID", "Trigger Level", "Instrument", "Strike", "Expiry", 
        "Lots", "Quantity", "Entry Timing", "Entry Price", "Entry Nifty", 
        "Exit Timing", "Exit Price", "Exit Nifty", "Exit Reason", 
        "PnL (Rupees)", "Is Paper Trade",
        "Post-Exit High", "Post-Exit High Time",
        "Post-Exit Low", "Post-Exit Low Time"
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
            post_exit_high = float(matching_exit.post_exit_high) if matching_exit.post_exit_high is not None else ""
            post_exit_high_time = matching_exit.post_exit_high_time.isoformat() if matching_exit.post_exit_high_time is not None else ""
            post_exit_low = float(matching_exit.post_exit_low) if matching_exit.post_exit_low is not None else ""
            post_exit_low_time = matching_exit.post_exit_low_time.isoformat() if matching_exit.post_exit_low_time is not None else ""
        else:
            exit_time_str = "OPEN"
            exit_price_val = ""
            exit_nifty_val = ""
            exit_reason_str = "OPEN"
            pnl_val = ""
            post_exit_high = ""
            post_exit_high_time = ""
            post_exit_low = ""
            post_exit_low_time = ""

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
            entry.is_paper_trade,
            post_exit_high,
            post_exit_high_time,
            post_exit_low,
            post_exit_low_time
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
    end_time: str | None = Query(default=None, description="HH:MM format"),
    trade_only: bool = Query(default=True, description="Filter for trade execution logs only"),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    import os
    import re
    from datetime import time, timedelta, datetime
    from fastapi import HTTPException
    from app.models.models import StrategyConfig

    log_path = "trade_engine.log"
    if not os.path.exists(log_path):
        return {"logs": []}

    # Resolve default end_time dynamically based on user's square-off configuration
    if not end_time:
        cfg = db.query(StrategyConfig).filter(
            StrategyConfig.user_id == user.id,
            StrategyConfig.is_active == True
        ).first()
        if cfg and cfg.squareoff_time:
            try:
                # Add 1 hour buffer to square-off time to capture final square-off actions
                h, m = map(int, cfg.squareoff_time.split(":"))
                # Use a dummy date to handle time addition safely
                dt = datetime.combine(datetime.min.date(), time(h, m)) + timedelta(hours=1)
                end_time = dt.time().strftime("%H:%M")
            except Exception:
                end_time = "12:30"
        else:
            end_time = "12:30"

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

    if trade_only:
        trade_indicators = ["app.core", "BUY", "EXIT", "SQUAREOFF", "force squareoff", "Target", "Stop Loss", "entered", "reset_daily", "daily_reset"]
        filtered_lines = [
            line for line in filtered_lines
            if any(ind.lower() in line.lower() for ind in trade_indicators)
        ]

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


@router.get("/reports")
def list_reports(user: User = Depends(require_auth)):
    """List all generated PDF reports in the logs/reports folder."""
    import os
    reports_dir = os.path.join("logs", "reports")
    if not os.path.exists(reports_dir):
        return {"reports": []}
        
    files = []
    for f in os.listdir(reports_dir):
        if f.endswith(".pdf") and f"_{user.id}_" in f:
            path = os.path.join(reports_dir, f)
            stat = os.stat(path)
            parts = f.replace(".pdf", "").split("_")
            report_type = parts[0]
            report_date = parts[3] if len(parts) >= 4 else ""
            
            files.append({
                "filename": f,
                "type": report_type,
                "date": report_date,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
            
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return {"reports": files}


@router.get("/reports/download")
def download_report(filename: str, user: User = Depends(require_auth)):
    """Download a specific PDF report."""
    import os
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    if f"_{user.id}_" not in filename:
        raise HTTPException(status_code=403, detail="Access denied")
        
    reports_dir = os.path.join("logs", "reports")
    filepath = os.path.join(reports_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report not found")
        
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename
    )


@router.post("/reports/trigger-daily")
async def trigger_daily_report(report_date: date | None = None, user: User = Depends(require_auth)):
    """Trigger manual daily report generation for testing."""
    from app.services.reporting import send_daily_report
    from app.core.time_rules import today_ist
    target = report_date or today_ist()
    await send_daily_report(user.id, target)
    return {"status": "triggered", "date": target.isoformat()}
