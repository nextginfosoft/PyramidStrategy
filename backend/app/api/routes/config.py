from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import StrategyConfig, ApiConfig
from app.schemas.schemas import StrategyConfigCreate, StrategyConfigResponse, ApiConfigUpdate, ApiConfigResponse
from app.services.encryption import encrypt, mask_key
from app.core.strategy_engine import engine
from loguru import logger

router = APIRouter(prefix="/config", tags=["config"])


# ── Strategy Levels ───────────────────────────────────────────────────────────

@router.get("/strategy", response_model=StrategyConfigResponse)
def get_strategy_config(db: Session = Depends(get_db)):
    cfg = db.query(StrategyConfig).order_by(StrategyConfig.id.desc()).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="No strategy config found. Please create one.")
    return cfg


@router.post("/strategy", response_model=StrategyConfigResponse)
def create_strategy_config(payload: StrategyConfigCreate, db: Session = Depends(get_db)):
    # Deactivate existing configs
    db.query(StrategyConfig).update({"is_active": False})

    cfg = StrategyConfig(
        r1=payload.r1, r2=payload.r2, r3=payload.r3,
        s1=payload.s1, s2=payload.s2, s3=payload.s3,
        lot_size=payload.lot_size,
        target_points=payload.target_points,
        sl_points=payload.sl_points,
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    # Push new config to running engine
    engine.load_config({
        "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
        "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
        "lot_size": cfg.lot_size,
        "target_points": float(cfg.target_points),
        "sl_points": float(cfg.sl_points),
    })

    logger.info(f"Strategy config saved: R1={cfg.r1} R2={cfg.r2} R3={cfg.r3} | S1={cfg.s1} S2={cfg.s2} S3={cfg.s3}")
    return cfg


@router.put("/strategy", response_model=StrategyConfigResponse)
def update_strategy_config(payload: StrategyConfigCreate, db: Session = Depends(get_db)):
    """Update levels — alias for POST (always creates a new active config)."""
    return create_strategy_config(payload, db)


# ── API Keys (encrypted storage) ──────────────────────────────────────────────

@router.post("/api-keys")
def save_api_key(payload: ApiConfigUpdate, db: Session = Depends(get_db)):
    existing = db.query(ApiConfig).filter(ApiConfig.provider == payload.provider).first()

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
            provider=payload.provider,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            extra_config=payload.extra_config,
        )
        db.add(existing)

    db.commit()
    logger.info(f"API key saved for provider: {payload.provider}")

    # Hot-reload AI/Telegram service if relevant provider updated
    if payload.provider in ("openai", "anthropic", "gemini"):
        from app.services.ai_service import ai_service
        ai_service.load_from_db()
    elif payload.provider == "telegram":
        from app.services.notification import notification_service
        notification_service.load_from_db()
    elif payload.provider == "zerodha":
        from app.api.routes.auth import _load_kite_credentials_from_db
        _load_kite_credentials_from_db()

    return {"status": "saved", "provider": payload.provider}


@router.get("/api-keys", response_model=list[ApiConfigResponse])
def list_api_keys(db: Session = Depends(get_db)):
    configs = db.query(ApiConfig).all()
    result = []
    for cfg in configs:
        masked = None
        if cfg.api_key_encrypted:
            from app.services.encryption import decrypt
            raw = decrypt(cfg.api_key_encrypted)
            masked = mask_key(raw)
        result.append(ApiConfigResponse(
            provider=cfg.provider,
            api_key_masked=masked,
            is_active=cfg.is_active,
        ))
    return result
