from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
import io
import csv
from decimal import Decimal
from loguru import logger

from app.db.database import get_db
from app.models.models import DailyPnL, User
from app.api.routes.session import require_auth

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/pnl-summary")
def get_pnl_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    # 1. Query all daily records inside the selected range
    records = (
        db.query(DailyPnL)
        .filter(
            DailyPnL.user_id == user.id,
            DailyPnL.trade_date >= start_date,
            DailyPnL.trade_date <= end_date,
        )
        .order_by(DailyPnL.trade_date.asc())
        .all()
    )

    if not records:
        return {
            "summary": {
                "total_net_pnl": 0.0,
                "total_gross_pnl": 0.0,
                "total_brokerage": 0.0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "total_days": 0,
                "winning_days": 0,
            },
            "daily_data": [],
            "equity_curve": [],
        }

    # 2. Compute Aggregates
    total_net = sum(r.net_pnl for r in records)
    total_gross = sum(r.gross_pnl for r in records)
    total_brokerage = sum(r.brokerage for r in records)
    winning_days = sum(1 for r in records if r.net_pnl > 0)
    total_days = len(records)
    win_rate = (winning_days / total_days * 100) if total_days > 0 else 0.0

    # 3. Calculate Drawdown and Equity Curve
    equity = Decimal("0.00")
    peak = Decimal("0.00")
    max_drawdown = Decimal("0.00")
    equity_curve = []

    for r in records:
        net_val = Decimal(str(r.net_pnl or 0))
        equity += net_val
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd
        equity_curve.append({
            "date": r.trade_date.isoformat(),
            "net_pnl": float(net_val),
            "cumulative_pnl": float(equity),
            "drawdown": float(dd),
        })

    return {
        "summary": {
            "total_net_pnl": float(total_net),
            "total_gross_pnl": float(total_gross),
            "total_brokerage": float(total_brokerage),
            "win_rate": round(win_rate, 2),
            "max_drawdown": float(max_drawdown),
            "total_days": total_days,
            "winning_days": winning_days,
        },
        "daily_data": [
            {
                "date": r.trade_date.isoformat(),
                "net_pnl": float(r.net_pnl),
                "gross_pnl": float(r.gross_pnl),
                "brokerage": float(r.brokerage),
                "total_trades": r.total_trades,
                "winning_trades": r.winning_trades,
                "ce_pnl": float(r.ce_pnl or 0),
                "pe_pnl": float(r.pe_pnl or 0),
            }
            for r in records
        ],
        "equity_curve": equity_curve,
    }


@router.get("/export-csv")
def export_pnl_csv(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    records = (
        db.query(DailyPnL)
        .filter(
            DailyPnL.user_id == user.id,
            DailyPnL.trade_date >= start_date,
            DailyPnL.trade_date <= end_date,
        )
        .order_by(DailyPnL.trade_date.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Date",
        "Gross PnL (Rs)",
        "Brokerage (Rs)",
        "Net PnL (Rs)",
        "Total Trades",
        "Winning Trades",
        "CE PnL (Rs)",
        "PE PnL (Rs)"
    ])

    for r in records:
        writer.writerow([
            r.trade_date.isoformat(),
            float(r.gross_pnl),
            float(r.brokerage),
            float(r.net_pnl),
            r.total_trades,
            r.winning_trades,
            float(r.ce_pnl or 0),
            float(r.pe_pnl or 0)
        ])

    output.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="pnl_report_{start_date}_to_{end_date}.csv"'
    }
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers=headers
    )
