"""
Session Auth — Phase 3 Multi-User Extension
JWT authentication mapping users dynamically to database records.
Provides registration, login, session check, and auth verification.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
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


def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Dependency: require authenticated user with admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


@router.post("/register")
def register(body: RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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

    # SendFox Email Marketing Automation Sync (Non-blocking background task)
    if "@" in body.username:
        try:
            from app.services.sendfox_service import add_sendfox_contact, send_sendfox_campaign
            background_tasks.add_task(add_sendfox_contact, body.username, body.username.split("@")[0], None, db)
            
            # Send immediate welcome campaign email
            welcome_html = f"""
            <h1>🚀 Welcome to DestinyAI!</h1>
            <p>Hi {body.username.split('@')[0]},</p>
            <p>Thank you for registering your free paper trading account with <strong>DestinyAI</strong> automated NIFTY options trading platform.</p>
            <p><strong>Your 3-Step Setup Checklist:</strong></p>
            <ol>
              <li>Log into your DestinyAI Dashboard.</li>
              <li>Configure your NIFTY Support & Resistance levels.</li>
              <li>Enable Smart Exit auto square-off and test strategy crossover execution live!</li>
            </ol>
            <p>Want live broker execution with Zerodha Kite? Use promo code <strong>PRO15</strong> at checkout for 15% OFF Pro plan!</p>
            <p>Happy Trading,<br>The DestinyAI Team</p>
            """
            background_tasks.add_task(send_sendfox_campaign, body.username, "🚀 Welcome to DestinyAI — Start Free Paper Trading Now!", welcome_html, db)
        except Exception as e:
            logger.warning(f"Failed to queue SendFox contact sync task: {e}")

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


class GoogleLoginRequest(BaseModel):
    token: str  # Google ID token or Access token


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Authenticate or register user using Google OAuth ID Token."""
    import urllib.request
    import json

    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Google token is required")

    # Verify ID token with Google's tokeninfo endpoint
    try:
        import httpx
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.error(f"Google token verification HTTP error {resp.status_code}: {resp.text}")
                raise HTTPException(status_code=400, detail=f"Google token rejected by Google (HTTP {resp.status_code})")
            res_data = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google token validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Google verification network error: {str(e)}")

    if "email" not in res_data:
        raise HTTPException(status_code=400, detail="Google token payload missing email")

    user_email = res_data["email"].strip().lower()
    google_sub = res_data.get("sub")
    name = res_data.get("name", user_email.split("@")[0])

    # Check if email belongs to configured Super Admin
    is_super_admin = (user_email == settings.SUPER_ADMIN_EMAIL.strip().lower())

    # Find existing user by email, google_id, or username
    user = db.query(User).filter(
        (User.email == user_email) | (User.google_id == google_sub) | (User.username == user_email.split("@")[0])
    ).first()

    if not user:
        # Auto-create user
        username_base = user_email.split("@")[0]
        user = User(
            username=username_base,
            hashed_password=get_password_hash("GOOGLE_SSO_USER_NO_PASSWORD"),
            email=user_email,
            google_id=google_sub,
            is_approved=True if is_super_admin else True,  # Auto-approve google users
            is_admin=is_super_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Google SSO: Created new user '{user.username}' (admin={is_super_admin})")
    else:
        # Update existing user
        user.email = user_email
        user.google_id = google_sub
        if is_super_admin:
            user.is_admin = True
            user.is_approved = True
        db.commit()
        logger.info(f"Google SSO: Existing user '{user.username}' logged in (admin={user.is_admin})")

    jwt_token = create_token(str(user.id))
    return TokenResponse(access_token=jwt_token)
