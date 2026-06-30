"""
Admin Routes — Manage User Approvals and Privileges
Enforces require_admin route guards and Super Admin safety rules.
"""

from fastapi import APIRouter, Depends, HTTPException, status
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
                f"✅ *PyramidStrategy ACTIVATED*\nYour account has been approved by the administrator. "
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
