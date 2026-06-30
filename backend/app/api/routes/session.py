"""
Session Auth — Phase 3 Multi-User Extension
JWT authentication mapping users dynamically to database records.
Provides registration, login, session check, and auth verification.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from loguru import logger
import bcrypt
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.models.models import User

router = APIRouter(prefix="/session", tags=["session"])
security = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = JWT_EXPIRE_HOURS * 3600


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_token(user_id_str: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id_str, "exp": expire},
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[int]:
    """Verify JWT token and return user_id (int) or None."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        return int(user_id_str) if user_id_str else None
    except (JWTError, ValueError):
        return None


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency: require valid JWT. Returns database User object."""
    user_id = verify_token(credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please login",
            headers={"WWW-Authenticate": "Bearer"},
        )
    users = db.query(User).filter(User.id == user_id).all()
    user = users[0] if users else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending administrator approval",
        )
    return user


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    if len(body.username.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long",
        )
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long",
        )

    existing_list = db.query(User).filter(User.username == body.username).all()
    existing = existing_list[0] if existing_list else None
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Determine automatic super admin promotion
    is_admin = False
    is_approved = False
    if body.username == settings.SUPER_ADMIN_USERNAME:
        is_admin = True
        is_approved = True

    hashed = get_password_hash(body.password)
    new_user = User(
        username=body.username,
        hashed_password=hashed,
        is_approved=is_approved,
        is_admin=is_admin,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: '{new_user.username}' (id={new_user.id}, approved={is_approved}, admin={is_admin})")

    # Send notification alert to the administrator for moderation
    if not is_approved:
        try:
            from app.services.notification import get_user_notification_service
            import asyncio
            ns = get_user_notification_service(1)  # Admin channel
            ns.load_from_db()
            asyncio.create_task(ns._send(
                f"🔔 *NEW USER SIGNUP PENDING*:\n"
                f"• Username: `{new_user.username}`\n"
                f"• User ID: `{new_user.id}`\n"
                f"Awaiting administrator approval."
            ))
        except Exception as e:
            logger.warning(f"Failed to send admin signup notification: {e}")

    return {
        "status": "registered",
        "username": new_user.username,
        "is_approved": is_approved,
        "is_admin": is_admin
    }


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and get JWT token."""
    users = db.query(User).filter(User.username == body.username).all()
    user = users[0] if users else None
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_token(str(user.id))
    logger.info(f"User '{user.username}' logged in")
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout():
    """Client-side logout (discard token on frontend)."""
    return {"status": "logged_out", "message": "Token discarded on client side"}


@router.get("/me")
def get_me(user: User = Depends(require_auth)):
    """Return current authenticated user info."""
    return {
        "username": user.username,
        "authenticated": True,
        "is_approved": user.is_approved,
        "is_admin": user.is_admin
    }


@router.get("/check")
def check_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: Session = Depends(get_db)):
    """Non-throwing auth check — returns authenticated status."""
    user_id = verify_token(credentials)
    if user_id:
        users = db.query(User).filter(User.id == user_id).all()
        user = users[0] if users else None
        if user:
            return {
                "authenticated": True,
                "username": user.username,
                "is_approved": user.is_approved,
                "is_admin": user.is_admin
            }
    return {"authenticated": False, "username": None, "is_approved": False, "is_admin": False}
