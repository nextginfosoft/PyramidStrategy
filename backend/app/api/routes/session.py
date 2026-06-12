"""
Session Auth — Phase 3
Simple single-user JWT authentication for the PyramidStrategy app.
Protects Settings and sensitive endpoints from unauthorized access.

Default credentials (change via .env):
  USERNAME = admin
  PASSWORD = pyramid123

POST /session/login   → returns JWT token
POST /session/logout  → client discards token
GET  /session/me      → current user info
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from loguru import logger

from app.config import settings

router = APIRouter(prefix="/session", tags=["session"])
security = HTTPBearer(auto_error=False)

# Single-user credentials (configurable via .env)
APP_USERNAME = "admin"
APP_PASSWORD = "pyramid123"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = JWT_EXPIRE_HOURS * 3600


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": username, "exp": expire},
        settings.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[str]:
    """Dependency: verify JWT token. Returns username or None."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def require_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """Dependency: require valid JWT. Raises 401 if missing/invalid."""
    username = verify_token(credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please login",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Authenticate and get JWT token."""
    if body.username != APP_USERNAME or body.password != APP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_token(body.username)
    logger.info(f"User '{body.username}' logged in")
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout():
    """Client-side logout (discard token on frontend)."""
    return {"status": "logged_out", "message": "Token discarded on client side"}


@router.get("/me")
def get_me(username: str = Depends(require_auth)):
    """Return current authenticated user info."""
    return {"username": username, "authenticated": True}


@router.get("/check")
def check_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Non-throwing auth check — returns authenticated status."""
    username = verify_token(credentials)
    return {"authenticated": username is not None, "username": username}
