"""
Admin Routes ΓÇö Manage User Approvals and Privileges
Enforces require_admin route guards and Super Admin safety rules.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.models.models import User, StrategyConfig, Trade, ApiConfig, DailyPnL, AuditLog, AISuggestion
from app.api.routes.session import require_auth
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


class UserResponse(BaseModel):
    id: int
    username: str
    is_approved: bool
    is_admin: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Dependency to assert the user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Admin privileges required",
        )
    return current_user


@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """List all registered users."""
    return db.query(User).order_by(User.id.asc()).all()


@router.post("/users/{target_id}/approve")
def approve_user(target_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Approve a user registration, enabling them to log in."""
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Super admin protection: cannot approve/unapprove self
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot toggle approval status for your own active account")

    user.is_approved = not user.is_approved
    db.commit()
    
    if user.is_approved:
        # Try to send notification to the approved user
        try:
            from app.services.notification import get_user_notification_service
            ns = get_user_notification_service(user.id)
            ns.load_from_db()
            import asyncio
            asyncio.create_task(ns._send(
                f"Γ£à *PyramidStrategy ACTIVATED*\nYour account has been approved by the administrator. "
                f"You can now log in and deploy your strategy."
            ))
        except Exception:
            pass

    return {"status": "success", "username": user.username, "is_approved": user.is_approved}


@router.post("/users/{target_id}/toggle-admin")
def toggle_admin(target_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Toggle administrator privileges for a user."""
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Prevent other admins from demoting super admin configured in .env
    if user.username == settings.SUPER_ADMIN_USERNAME and current_user.username != settings.SUPER_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Only the Super Admin can demote or toggle privileges of this account")
        
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot toggle admin privileges for your own active session")

    user.is_admin = not user.is_admin
    db.commit()
    return {"status": "success", "username": user.username, "is_admin": user.is_admin}


@router.delete("/users/{target_id}")
def delete_user(target_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Delete a user account and purge all their related config/data."""
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.username == settings.SUPER_ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail="Cannot delete the Super Admin master account")
        
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own active session")

    # Clean up associated DB tables to avoid cascade constraint violations
    db.query(StrategyConfig).filter(StrategyConfig.user_id == target_id).delete()
    db.query(Trade).filter(Trade.user_id == target_id).delete()
    db.query(ApiConfig).filter(ApiConfig.user_id == target_id).delete()
    db.query(DailyPnL).filter(DailyPnL.user_id == target_id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == target_id).delete()
    db.query(AISuggestion).filter(AISuggestion.user_id == target_id).delete()
    
    db.delete(user)
    db.commit()
    return {"status": "success", "message": f"User {user.username} deleted and purged successfully"}


# ΓöÇΓöÇ Multi-User Admin Extensions ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

from datetime import date
from decimal import Decimal
from app.services.encryption import encrypt
from app.api.routes.session import get_password_hash
from app.core.engine_manager import engine_manager


class AdminCreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False
    
    # Zerodha details
    zerodha_api_key: Optional[str] = None
    zerodha_api_secret: Optional[str] = None
    zerodha_username: Optional[str] = None
    zerodha_password: Optional[str] = None
    zerodha_totp_secret: Optional[str] = None


class BulkSyncLevelsRequest(BaseModel):
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


@router.post("/users/create", status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new user with dashboard login and Zerodha credentials."""
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username is already registered")

    try:
        new_user = User(
            username=payload.username,
            hashed_password=get_password_hash(payload.password),
            is_approved=True,  # Approved by default when admin creates them
            is_admin=payload.is_admin
        )
        db.add(new_user)
        db.flush()

        if payload.zerodha_api_key and payload.zerodha_api_secret:
            extra_cfg = {
                "username": payload.zerodha_username,
                "password_encrypted": encrypt(payload.zerodha_password) if payload.zerodha_password else None,
                "totp_secret_encrypted": encrypt(payload.zerodha_totp_secret) if payload.zerodha_totp_secret else None,
            }
            api_cfg = ApiConfig(
                user_id=new_user.id,
                provider="zerodha",
                api_key_encrypted=encrypt(payload.zerodha_api_key),
                api_secret_encrypted=encrypt(payload.zerodha_api_secret),
                extra_config=extra_cfg,
                is_active=True
            )
            db.add(api_cfg)

        default_strategy = StrategyConfig(
            user_id=new_user.id,
            r1=23000.0, r2=23100.0, r3=23200.0,
            s1=22900.0, s2=22800.0, s3=22700.0,
            lot_size=75,
            target_points=20.0,
            sl_points=10.0,
            paper_trade=True,
            squareoff_time="11:30",
            is_active=True
        )
        db.add(default_strategy)
        
        db.commit()
        return {"status": "success", "user_id": new_user.id, "username": new_user.username}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/strategy/sync-levels")
def sync_levels_globally(
    payload: BulkSyncLevelsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Sync R1-R3 / S1-S3 levels across all active traders."""
    active_users = db.query(User).filter(User.is_approved == True).all()
    updated_count = 0

    for user in active_users:
        current_cfg = db.query(StrategyConfig).filter(
            StrategyConfig.user_id == user.id,
            StrategyConfig.is_active == True
        ).order_by(StrategyConfig.id.desc()).first()

        lot_size = current_cfg.lot_size if current_cfg else 75
        target_points = current_cfg.target_points if current_cfg else 20
        sl_points = current_cfg.sl_points if current_cfg else 10
        paper_trade = current_cfg.paper_trade if current_cfg else True
        squareoff_time = current_cfg.squareoff_time if current_cfg else "11:30"

        db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id).update({"is_active": False})

        new_cfg = StrategyConfig(
            user_id=user.id,
            r1=payload.r1, r2=payload.r2, r3=payload.r3,
            s1=payload.s1, s2=payload.s2, s3=payload.s3,
            lot_size=lot_size,
            target_points=target_points,
            sl_points=sl_points,
            paper_trade=paper_trade,
            squareoff_time=squareoff_time,
            is_active=True
        )
        db.add(new_cfg)
        db.flush()

        user_engine = engine_manager.get_engine(user.id)
        user_engine.load_config({
            "r1": float(payload.r1), "r2": float(payload.r2), "r3": float(payload.r3),
            "s1": float(payload.s1), "s2": float(payload.s2), "s3": float(payload.s3),
            "lot_size": lot_size,
            "target_points": float(target_points),
            "sl_points": float(sl_points),
            "paper_trade": paper_trade,
            "squareoff_time": squareoff_time,
        })
        updated_count += 1

    db.commit()
    return {"status": "success", "synced_users": updated_count}


@router.post("/strategy/emergency-exit-all")
async def admin_emergency_exit_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: Force-close ALL open positions for every active user engine concurrently.

    Returns a summary with the total number of users exited and a per-user breakdown.
    """
    from decimal import Decimal
    from loguru import logger

    logger.warning(
        f"ADMIN EMERGENCY EXIT ALL triggered by admin user '{current_user.username}' (id={current_user.id})"
    )

    results = await engine_manager.emergency_exit_all()

    # Broadcast updated status to each affected user's WebSocket clients
    for entry in results:
        uid = entry.get("user_id")
        if uid is None:
            continue
        try:
            user_engine = engine_manager.get_engine(uid)
            nifty_price = user_engine.last_nifty_price or Decimal("23200.00")
            await user_engine._broadcast_status(nifty_price)
        except Exception as exc:
            logger.warning(f"Post-emergency broadcast failed for user {uid}: {exc}")

    total_exited = sum(
        r.get("exited_count", 0) for r in results if r.get("status") == "emergency_exited"
    )
    errored = [r for r in results if r.get("status") == "error"]

    return {
        "status": "ok",
        "users_processed": len(results),
        "total_positions_exited": total_exited,
        "errors": len(errored),
        "results": results,
    }


@router.get("/users/status")
def get_all_users_status(
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_admin)
):
    """Get active session, strategy state, and Kite connection status for all traders."""
    traders = db.query(User).filter(User.is_approved == True).all()
    status_report = []

    for trader in traders:
        engine = engine_manager.get_engine(trader.id)
        engine_status = engine.get_full_status()
        
        status_report.append({
            "user_id": trader.id,
            "username": trader.username,
            "is_admin": trader.is_admin,
            "engine": {
                "is_running": engine_status.get("is_running", False),
                "paper_trade": engine_status.get("paper_trade", True),
                "ce_state": engine_status.get("ce", {}).get("state", "IDLE"),
                "pe_state": engine_status.get("pe", {}).get("state", "IDLE"),
                "ce_lots": engine_status.get("ce", {}).get("lots", 0),
                "pe_lots": engine_status.get("pe", {}).get("lots", 0),
                "realized_pnl": (
                    engine_status.get("ce", {}).get("realized_pnl", 0.0)
                    + engine_status.get("pe", {}).get("realized_pnl", 0.0)
                ),
                "unrealized_pnl": (
                    (engine_status.get("ce", {}).get("unrealized_pnl") or 0.0)
                    + (engine_status.get("pe", {}).get("unrealized_pnl") or 0.0)
                )
            },
            "kite": {
                "authenticated": engine_status.get("health", {}).get("authenticated", False),
                "ticker_connected": engine_status.get("health", {}).get("ticker_connected", False),
                "last_nifty_tick": engine_status.get("health", {}).get("last_nifty_tick_seconds_ago"),
                "last_api_error": engine_status.get("health", {}).get("last_api_error"),
                "available_margin": engine_status.get("health", {}).get("available_margin")
            }
        })

    return status_report


@router.get("/users/{target_id}/analytics")
def get_individual_user_analytics(
    target_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Fetch historical performance analytics for a specific user."""
    target_user = db.query(User).filter(User.id == target_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    records = (
        db.query(DailyPnL)
        .filter(
            DailyPnL.user_id == target_id,
            DailyPnL.trade_date >= start_date,
            DailyPnL.trade_date <= end_date,
        )
        .order_by(DailyPnL.trade_date.asc())
        .all()
    )

    if not records:
        return {
            "username": target_user.username,
            "summary": {
                "total_net_pnl": 0.0,
                "total_gross_pnl": 0.0,
                "total_brokerage": 0.0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "total_days": 0,
            },
            "daily_data": [],
            "equity_curve": [],
        }

    total_net = sum(r.net_pnl for r in records)
    total_gross = sum(r.gross_pnl for r in records)
    total_brokerage = sum(r.brokerage for r in records)
    winning_days = sum(1 for r in records if r.net_pnl > 0)
    total_days = len(records)
    win_rate = (winning_days / total_days * 100) if total_days > 0 else 0.0

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
        "username": target_user.username,
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
            } for r in records
        ],
        "equity_curve": equity_curve,
    }


@router.post("/users/{target_id}/test-credentials")
def admin_test_user_credentials(
    target_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Test programmatic login verification for a user's stored Zerodha credentials."""
    from app.services.encryption import decrypt
    from app.api.routes.auth import _load_kite_credentials_from_db
    from app.services.kite_service import get_user_kite_service
    from loguru import logger

    row = db.query(ApiConfig).filter(
        ApiConfig.user_id == target_id,
        ApiConfig.provider == "zerodha",
        ApiConfig.is_active == True,
    ).first()

    if not row or not row.extra_config:
        raise HTTPException(
            status_code=400,
            detail="Zerodha credentials not found or not configured."
        )

    extra = row.extra_config
    username = extra.get("username")
    password_enc = extra.get("password_encrypted")
    totp_secret_enc = extra.get("totp_secret_encrypted")

    if not username or not password_enc or not totp_secret_enc:
        raise HTTPException(
            status_code=400,
            detail="Test connection requires Username, Password, and TOTP Secret."
        )

    if not _load_kite_credentials_from_db(target_id):
        raise HTTPException(
            status_code=400,
            detail="Failed to load and configure Kite service with stored API Key/Secret."
        )

    try:
        password = decrypt(password_enc)
        totp_secret = decrypt(totp_secret_enc)
        
        user_kite = get_user_kite_service(target_id)
        
        # Trigger programmatic login attempt
        access_token = user_kite.auto_login(username, password, totp_secret)
        
        # Save access token encrypted in DB
        extra_updated = dict(row.extra_config or {})
        extra_updated["access_token_encrypted"] = encrypt(access_token)
        row.extra_config = extra_updated
        db.commit()
        
        return {
            "status": "success",
            "message": "Zerodha credentials verified! Programmatic connection established."
        }
    except Exception as e:
        logger.error(f"Admin test credentials failed for User {target_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Verification failed: {str(e)}"
        )


class AdminUpdateUserRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    
    # Zerodha details
    zerodha_api_key: Optional[str] = None
    zerodha_api_secret: Optional[str] = None
    zerodha_username: Optional[str] = None
    zerodha_password: Optional[str] = None
    zerodha_totp_secret: Optional[str] = None


@router.put("/users/{target_id}")
def admin_update_user(
    target_id: int,
    payload: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update a user's details and Zerodha credentials."""
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Prevent other admins from modifying super admin
    if user.username == settings.SUPER_ADMIN_USERNAME and current_user.username != settings.SUPER_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Only the Super Admin can modify the Super Admin account")

    # Update username if changed and not duplicate
    if payload.username and payload.username != user.username:
        existing = db.query(User).filter(User.username == payload.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username is already registered")
        user.username = payload.username

    # Update password if provided
    if payload.password and payload.password.strip():
        user.hashed_password = get_password_hash(payload.password)

    # Update admin role
    if payload.is_admin is not None:
        if user.id == current_user.id and payload.is_admin is False:
            raise HTTPException(status_code=400, detail="Cannot demote yourself from admin")
        user.is_admin = payload.is_admin

    # Update Zerodha API credentials
    has_zerodha = (
        payload.zerodha_api_key is not None
        or payload.zerodha_api_secret is not None
        or payload.zerodha_username is not None
        or payload.zerodha_password is not None
        or payload.zerodha_totp_secret is not None
    )

    if has_zerodha:
        api_cfg = db.query(ApiConfig).filter(
            ApiConfig.user_id == target_id,
            ApiConfig.provider == "zerodha"
        ).first()

        if not api_cfg:
            api_cfg = ApiConfig(
                user_id=target_id,
                provider="zerodha",
                is_active=True,
                extra_config={}
            )
            db.add(api_cfg)

        if payload.zerodha_api_key and payload.zerodha_api_key.strip():
            api_cfg.api_key_encrypted = encrypt(payload.zerodha_api_key)
        if payload.zerodha_api_secret and payload.zerodha_api_secret.strip():
            api_cfg.api_secret_encrypted = encrypt(payload.zerodha_api_secret)

        extra = dict(api_cfg.extra_config or {})
        if payload.zerodha_username is not None:
            extra["username"] = payload.zerodha_username
        if payload.zerodha_password and payload.zerodha_password.strip():
            extra["password_encrypted"] = encrypt(payload.zerodha_password)
        if payload.zerodha_totp_secret and payload.zerodha_totp_secret.strip():
            extra["totp_secret_encrypted"] = encrypt(payload.zerodha_totp_secret)
        
        api_cfg.extra_config = extra

        # Hot-reload user specific settings
        try:
            from app.api.routes.auth import _load_kite_credentials_from_db
            _load_kite_credentials_from_db(target_id)
        except Exception:
            pass

    db.commit()
    return {"status": "success", "message": f"User {user.username} updated successfully"}


class AdminTestCredentialsDryRunRequest(BaseModel):
    zerodha_api_key: str
    zerodha_api_secret: str
    zerodha_username: str
    zerodha_password: str
    zerodha_totp_secret: str


@router.post("/users/test-credentials-dry-run")
def admin_test_credentials_dry_run(
    payload: AdminTestCredentialsDryRunRequest,
    current_user: User = Depends(require_admin)
):
    """Test login verification for arbitrary Zerodha credentials without modifying DB."""
    from app.services.kite_service import KiteService
    from loguru import logger

    temp_kite = KiteService(user_id=0)
    
    try:
        temp_kite.configure(payload.zerodha_api_key, payload.zerodha_api_secret)
        # Attempt auto-login
        access_token = temp_kite.auto_login(
            payload.zerodha_username, 
            payload.zerodha_password, 
            payload.zerodha_totp_secret
        )
        return {
            "status": "success",
            "message": "Zerodha connection verified successfully! All credentials are correct."
        }
    except Exception as e:
        logger.error(f"Dry-run test credentials failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Verification failed: {str(e)}"
        )
