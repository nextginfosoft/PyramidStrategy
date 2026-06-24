"""
Reporting Service — Automated Daily Reporting
─────────────────────────────────────────────
Generates and delivers Daily EOD reports and Weekly summaries via PDF, Telegram, or WhatsApp.
Estimates brokerage and updates the DailyPnL table.
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from loguru import logger
import httpx
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.models import User, Trade, DailyPnL, AISuggestion, AuditLog, ApiConfig
from app.services.notification import get_user_notification_service
from app.services.whatsapp import get_user_whatsapp_service
from app.services.pdf_generator import build_daily_report_pdf, build_weekly_report_pdf
from app.core.time_rules import to_ist_str


def get_user_reporting_config(user_id: int, db: Session) -> dict:
    """Retrieve reporting configurations (format) for user."""
    cfg = db.query(ApiConfig).filter(
        ApiConfig.user_id == user_id,
        ApiConfig.provider == "reporting",
        ApiConfig.is_active == True
    ).first()
    if cfg and cfg.extra_config:
        return cfg.extra_config
    return {"format": "telegram"}  # Default fallback


def generate_daily_report(user_id: int, target_date: date, db: Session) -> str:
    """
    Fetch today's trades, strategy decisions, P&L, AI suggestions, and format the EOD report.
    """
    # Fetch all trades for today
    trades = db.query(Trade).filter(
        Trade.user_id == user_id,
        Trade.trade_date == target_date
    ).order_by(Trade.created_at.asc()).all()

    # Calculate statistics
    exits = [t for t in trades if t.action == "EXIT"]
    gross_pnl = sum((t.pnl for t in exits if t.pnl is not None), Decimal("0"))
    total_trades = len(trades)
    
    # Zerodha flat estimation: ₹20 per trade execution (buy or exit)
    brokerage = Decimal(str(total_trades * 20.0))
    net_pnl = gross_pnl - brokerage
    winning_trades = sum(1 for t in exits if t.pnl is not None and t.pnl > 0)
    losing_trades = len(exits) - winning_trades

    ce_exits = [t for t in exits if t.side == "CE"]
    pe_exits = [t for t in exits if t.side == "PE"]
    ce_pnl = sum((t.pnl for t in ce_exits if t.pnl is not None), Decimal("0"))
    pe_pnl = sum((t.pnl for t in pe_exits if t.pnl is not None), Decimal("0"))

    # Save or update DailyPnL record
    daily_pnl_record = db.query(DailyPnL).filter(
        DailyPnL.user_id == user_id,
        DailyPnL.trade_date == target_date
    ).first()

    if not daily_pnl_record:
        daily_pnl_record = DailyPnL(
            user_id=user_id,
            trade_date=target_date,
            gross_pnl=gross_pnl,
            brokerage=brokerage,
            net_pnl=net_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            ce_pnl=ce_pnl,
            pe_pnl=pe_pnl
        )
        db.add(daily_pnl_record)
    else:
        daily_pnl_record.gross_pnl = gross_pnl
        daily_pnl_record.brokerage = brokerage
        daily_pnl_record.net_pnl = net_pnl
        daily_pnl_record.total_trades = total_trades
        daily_pnl_record.winning_trades = winning_trades
        daily_pnl_record.ce_pnl = ce_pnl
        daily_pnl_record.pe_pnl = pe_pnl
    
    db.commit()

    # Get Audit Log decisions for today (Strategy Decisions)
    audit_logs = db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.created_at >= target_date,
        AuditLog.created_at < target_date + timedelta(days=1)
    ).order_by(AuditLog.created_at.asc()).all()

    # Get AI suggestions for today
    ai_suggestions = db.query(AISuggestion).filter(
        AISuggestion.user_id == user_id,
        AISuggestion.trade_date == target_date
    ).order_by(AISuggestion.created_at.asc()).all()

    # Format Telegram/WhatsApp Message
    date_str = target_date.strftime("%d-%b-%Y")
    sign = "+" if net_pnl >= 0 else ""
    pnl_emoji = "💰" if net_pnl >= 0 else "🛑"

    msg = (
        f"📋 *PyramidStrategy Daily EOD Report* — {date_str}\n"
        f"====================================\n\n"
        f"{pnl_emoji} *P&L Summary*:\n"
        f"• *Gross P&L*: ₹{gross_pnl:,.2f}\n"
        f"• *Est. Brokerage*: ₹{brokerage:,.2f}\n"
        f"• *Net P&L*: `{sign}₹{net_pnl:,.2f}`\n"
        f"• *Exits*: {len(exits)} | *Wins*: {winning_trades} | *Losses*: {losing_trades}\n\n"
        f"📊 *Leg Breakdown*:\n"
        f"• *CE P&L*: ₹{ce_pnl:,.2f}\n"
        f"• *PE P&L*: ₹{pe_pnl:,.2f}\n\n"
    )

    if trades:
        msg += "📈 *Trades Log*:\n"
        for t in trades:
            time_str = to_ist_str(t.created_at, "%I:%M %p")
            if t.action == "BUY":
                msg += f"• `{time_str}` 🟢 *BUY* `{t.instrument}` | Lots: {t.lots} @ ₹{t.avg_price:.2f}\n"
            else:
                pnl_sign = "+" if t.pnl >= 0 else ""
                msg += f"• `{time_str}` 🔴 *EXIT ({t.status})* `{t.instrument}` | P&L: {pnl_sign}₹{t.pnl:.2f}\n"
        msg += "\n"
    else:
        msg += "📭 *No trades executed today.*\n\n"

    if audit_logs:
        msg += "⚙️ *Strategy Decisions & Triggers*:\n"
        for log in audit_logs:
            time_str = to_ist_str(log.created_at, "%I:%M %p")
            details_str = ""
            if log.details:
                if "msg" in log.details:
                    details_str = log.details["msg"]
                elif "reason" in log.details:
                    details_str = f"Reason: {log.details['reason']}"
                else:
                    details_str = str(log.details)
            msg += f"• `{time_str}` *{log.event_type}* | {log.side or ''} {log.level or ''} | Nifty: {log.nifty_price or '-'} | {details_str[:70]}\n"
        msg += "\n"

    if ai_suggestions:
        msg += "🤖 *AI Observations*:\n"
        for sugg in ai_suggestions:
            msg += f"• *{sugg.event} ({sugg.side or 'GEN'})*: {sugg.suggestion}\n"
        msg += "\n"
    
    return msg


def generate_weekly_report(user_id: int, monday_date: date, db: Session) -> str:
    """
    Fetch past week's daily P&L and generate a weekly summary briefing.
    Assumes running on a Monday, summarizing Mon-Fri of the prior week.
    """
    # Prior week start (Monday) and end (Friday)
    start_date = monday_date - timedelta(days=7)
    end_date = monday_date - timedelta(days=3)

    daily_pnls = db.query(DailyPnL).filter(
        DailyPnL.user_id == user_id,
        DailyPnL.trade_date >= start_date,
        DailyPnL.trade_date <= end_date
    ).order_by(DailyPnL.trade_date.asc()).all()

    total_gross = sum((p.gross_pnl for p in daily_pnls), Decimal("0"))
    total_brokerage = sum((p.brokerage for p in daily_pnls), Decimal("0"))
    total_net = sum((p.net_pnl for p in daily_pnls), Decimal("0"))
    total_trades = sum((p.total_trades for p in daily_pnls), 0)
    total_wins = sum((p.winning_trades for p in daily_pnls), 0)
    
    ce_total_pnl = sum((p.ce_pnl for p in daily_pnls), Decimal("0"))
    pe_total_pnl = sum((p.pe_pnl for p in daily_pnls), Decimal("0"))

    active_days = len(daily_pnls)
    winning_days = sum(1 for p in daily_pnls if p.net_pnl > 0)
    win_rate_days = (winning_days / active_days * 100) if active_days > 0 else 0.0

    start_str = start_date.strftime("%d-%b")
    end_str = end_date.strftime("%d-%b")
    sign = "+" if total_net >= 0 else ""
    pnl_emoji = "🏆" if total_net >= 0 else "🛑"

    msg = (
        f"📅 *PyramidStrategy Weekly Summary* — Week of {start_str} to {end_str}\n"
        f"====================================\n\n"
        f"{pnl_emoji} *Weekly P&L Stats*:\n"
        f"• *Gross P&L*: ₹{total_gross:,.2f}\n"
        f"• *Total Brokerage*: ₹{total_brokerage:,.2f}\n"
        f"• *Net P&L*: `{sign}₹{total_net:,.2f}`\n"
        f"• *Winning Days*: {winning_days}/{active_days} ({win_rate_days:.1f}% Win Rate)\n"
        f"• *Total Trades*: {total_trades} | *Win Trades*: {total_wins}\n\n"
        f"⚖️ *CE vs PE Leg Performance*:\n"
        f"• *CE Total P&L*: ₹{ce_total_pnl:,.2f}\n"
        f"• *PE Total P&L*: ₹{pe_total_pnl:,.2f}\n\n"
        f"📊 *Daily P&L Breakdown*:\n"
    )

    if daily_pnls:
        for p in daily_pnls:
            day_name = p.trade_date.strftime("%A")
            day_pnl_sign = "+" if p.net_pnl >= 0 else ""
            msg += f"• *{day_name}*: {day_pnl_sign}₹{p.net_pnl:.2f} (Net)\n"
    else:
        msg += "📭 *No trading activity recorded for last week.*\n"

    return msg


async def send_daily_report(user_id: int, target_date: date):
    """Generate, save, and deliver the daily report for target_date."""
    logger.info(f"Generating Daily EOD Report for User {user_id} on {target_date}")
    try:
        with SessionLocal() as db:
            rep_cfg = get_user_reporting_config(user_id, db)
            fmt = rep_cfg.get("format", "telegram")  # "telegram", "whatsapp", or "pdf"
            
            ns = get_user_notification_service(user_id)
            ws = get_user_whatsapp_service(user_id)
            
            # Make sure configurations are freshly loaded
            ns.load_from_db()
            ws.load_from_db()

            if fmt == "pdf":
                reports_dir = os.path.join("logs", "reports")
                os.makedirs(reports_dir, exist_ok=True)
                pdf_path = os.path.join(reports_dir, f"daily_report_{user_id}_{target_date}.pdf")
                build_daily_report_pdf(user_id, target_date, db, pdf_path)
                
                sent = False
                if ns.is_enabled():
                    url = f"https://api.telegram.org/bot{ns._bot_token}/sendDocument"
                    async with httpx.AsyncClient(timeout=20) as client:
                        with open(pdf_path, "rb") as f:
                            files = {"document": f}
                            data = {
                                "chat_id": ns._chat_id, 
                                "caption": f"📋 *PyramidStrategy Daily EOD Report* — {target_date.strftime('%d-%b-%Y')}"
                            }
                            resp = await client.post(url, data=data, files=files)
                            if resp.status_code == 200:
                                logger.info(f"Daily PDF Report sent to User {user_id} via Telegram")
                                sent = True
                            else:
                                logger.warning(f"Failed to send Daily PDF Report via Telegram: {resp.status_code} {resp.text}")
                
                if not sent and ws.is_enabled():
                    ws_success = await ws.send_document(pdf_path, f"Daily EOD Report — {target_date.strftime('%d-%b-%Y')}")
                    if ws_success:
                        logger.info(f"Daily PDF Report sent to User {user_id} via WhatsApp")
                        sent = True

                if not sent:
                    logger.warning(f"User {user_id}: PDF report generated but neither Telegram nor WhatsApp is enabled.")
                    
            elif fmt == "whatsapp":
                if ws.is_enabled():
                    msg = generate_daily_report(user_id, target_date, db)
                    await ws.send_message(msg)
                    logger.info(f"Daily EOD Report sent to User {user_id} via WhatsApp")
                else:
                    logger.warning(f"User {user_id}: WhatsApp format selected but WhatsApp notifications disabled.")
                    
            else:  # telegram (default)
                if ns.is_enabled():
                    msg = generate_daily_report(user_id, target_date, db)
                    await ns._send(msg)
                    logger.info(f"Daily EOD Report sent to User {user_id} via Telegram")
                else:
                    logger.warning(f"User {user_id}: Telegram format selected but Telegram notifications disabled.")
                    
    except Exception as e:
        logger.error(f"Failed to generate/send Daily EOD Report for User {user_id}: {e}", exc_info=True)


async def send_weekly_report(user_id: int, monday_date: date):
    """Generate and deliver the weekly summary for the week prior to monday_date."""
    logger.info(f"Generating Weekly Summary for User {user_id} on {monday_date}")
    try:
        with SessionLocal() as db:
            rep_cfg = get_user_reporting_config(user_id, db)
            fmt = rep_cfg.get("format", "telegram")  # "telegram", "whatsapp", or "pdf"
            
            ns = get_user_notification_service(user_id)
            ws = get_user_whatsapp_service(user_id)
            
            # Make sure configurations are freshly loaded
            ns.load_from_db()
            ws.load_from_db()

            if fmt == "pdf":
                reports_dir = os.path.join("logs", "reports")
                os.makedirs(reports_dir, exist_ok=True)
                pdf_path = os.path.join(reports_dir, f"weekly_report_{user_id}_{monday_date}.pdf")
                build_weekly_report_pdf(user_id, monday_date, db, pdf_path)
                
                sent = False
                if ns.is_enabled():
                    url = f"https://api.telegram.org/bot{ns._bot_token}/sendDocument"
                    async with httpx.AsyncClient(timeout=20) as client:
                        with open(pdf_path, "rb") as f:
                            files = {"document": f}
                            data = {
                                "chat_id": ns._chat_id, 
                                "caption": f"📅 *PyramidStrategy Weekly Summary* — Week of {(monday_date - timedelta(days=7)).strftime('%d-%b')}"
                            }
                            resp = await client.post(url, data=data, files=files)
                            if resp.status_code == 200:
                                logger.info(f"Weekly PDF Report sent to User {user_id} via Telegram")
                                sent = True
                            else:
                                logger.warning(f"Failed to send Weekly PDF Report via Telegram: {resp.status_code} {resp.text}")
                
                if not sent and ws.is_enabled():
                    ws_success = await ws.send_document(pdf_path, f"Weekly Report — Week of {(monday_date - timedelta(days=7)).strftime('%d-%b')}")
                    if ws_success:
                        logger.info(f"Weekly PDF Report sent to User {user_id} via WhatsApp")
                        sent = True

                if not sent:
                    logger.warning(f"User {user_id}: Weekly PDF report generated but neither Telegram nor WhatsApp is enabled.")
                    
            elif fmt == "whatsapp":
                if ws.is_enabled():
                    msg = generate_weekly_report(user_id, monday_date, db)
                    await ws.send_message(msg)
                    logger.info(f"Weekly Summary sent to User {user_id} via WhatsApp")
                else:
                    logger.warning(f"User {user_id}: WhatsApp format selected but WhatsApp notifications disabled.")
                    
            else:  # telegram (default)
                if ns.is_enabled():
                    msg = generate_weekly_report(user_id, monday_date, db)
                    await ns._send(msg)
                    logger.info(f"Weekly Summary sent to User {user_id} via Telegram")
                else:
                    logger.warning(f"User {user_id}: Telegram format selected but Telegram notifications disabled.")
                    
    except Exception as e:
        logger.error(f"Failed to generate/send Weekly Summary for User {user_id}: {e}", exc_info=True)
