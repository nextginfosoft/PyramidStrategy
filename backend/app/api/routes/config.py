from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import StrategyConfig, ApiConfig, User
from app.schemas.schemas import StrategyConfigCreate, StrategyConfigResponse, ApiConfigUpdate, ApiConfigResponse
from app.services.encryption import encrypt, decrypt, mask_key
from app.core.engine_manager import engine_manager
from app.api.routes.session import require_auth
from loguru import logger

router = APIRouter(prefix="/config", tags=["config"])


# ── Strategy Levels ───────────────────────────────────────────────────────────

@router.get("/strategy", response_model=StrategyConfigResponse)
def get_strategy_config(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    cfg = db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id).order_by(StrategyConfig.id.desc()).first()
    if not cfg:
        # Return a default initial config if none exists for this user
        return StrategyConfigResponse(
            id=0,
            r1=23170, r2=23220, r3=23250,
            s1=23070, s2=23025, s3=22950,
            lot_size=75,
            target_points=20,
            sl_points=10,
            paper_trade=True,
            is_active=False
        )
    return cfg


@router.post("/strategy", response_model=StrategyConfigResponse)
def create_strategy_config(payload: StrategyConfigCreate, db: Session = Depends(get_db), user: User = Depends(require_auth)):
    # Deactivate existing configs for this user
    db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id).update({"is_active": False})

    cfg = StrategyConfig(
        user_id=user.id,
        r1=payload.r1, r2=payload.r2, r3=payload.r3,
        s1=payload.s1, s2=payload.s2, s3=payload.s3,
        lot_size=payload.lot_size,
        target_points=payload.target_points,
        sl_points=payload.sl_points,
        paper_trade=payload.paper_trade,
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    # Push new config to running engine for this specific user
    user_engine = engine_manager.get_engine(user.id)
    user_engine.load_config({
        "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
        "lot_size": cfg.lot_size,
        "target_points": float(cfg.target_points),
        "sl_points": float(cfg.sl_points),
        "paper_trade": cfg.paper_trade,
    })

    logger.info(f"User {user.username} strategy config saved: R1={cfg.r1} R2={cfg.r2} R3={cfg.r3} | S1={cfg.s1} S2={cfg.s2} S3={cfg.s3} | paper_trade={cfg.paper_trade}")
    return cfg


@router.put("/strategy", response_model=StrategyConfigResponse)
def update_strategy_config(payload: StrategyConfigCreate, db: Session = Depends(get_db), user: User = Depends(require_auth)):
    """Update levels — alias for POST (always creates a new active config)."""
    return create_strategy_config(payload, db, user)


# ── API Keys (encrypted storage) ──────────────────────────────────────────────

@router.post("/api-keys")
def save_api_key(payload: ApiConfigUpdate, db: Session = Depends(get_db), user: User = Depends(require_auth)):
    existing = db.query(ApiConfig).filter(
        ApiConfig.user_id == user.id,
        ApiConfig.provider == payload.provider
    ).first()

    encrypted_key = encrypt(payload.api_key) if payload.api_key else None
    encrypted_secret = encrypt(payload.api_secret) if payload.api_secret else None

    if existing:
        if encrypted_key:
            existing.api_key_encrypted = encrypted_key
        if encrypted_secret:
            existing.api_secret_encrypted = encrypted_secret
        if payload.extra_config:
            existing.extra_config = payload.extra_config
    else:
        existing = ApiConfig(
            user_id=user.id,
            provider=payload.provider,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            extra_config=payload.extra_config,
        )
        db.add(existing)
    db.commit()
    logger.info(f"User {user.username}: API key saved for provider: {payload.provider}")

    # Hot-reload user specific settings
    if payload.provider == "zerodha":
        from app.api.routes.auth import _load_kite_credentials_from_db
        _load_kite_credentials_from_db(user.id)
    elif payload.provider == "telegram":
        from app.services.notification import get_user_notification_service
        get_user_notification_service(user.id).load_from_db()

    return {"status": "saved", "provider": payload.provider}





@router.get("/api-keys", response_model=list[ApiConfigResponse])
def list_api_keys(db: Session = Depends(get_db), user: User = Depends(require_auth)):
    configs = db.query(ApiConfig).filter(ApiConfig.user_id == user.id).all()
    result = []
    for cfg in configs:
        masked = None
        if cfg.api_key_encrypted:
            raw = decrypt(cfg.api_key_encrypted)
            masked = mask_key(raw)
        result.append(ApiConfigResponse(
            provider=cfg.provider,
            api_key_masked=masked,
            is_active=cfg.is_active,
        ))
    return result
