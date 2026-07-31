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

from datetime import datetime

@router.get("/strategy", response_model=StrategyConfigResponse)
def get_strategy_config(strategy_type: str = None, db: Session = Depends(get_db), user: User = Depends(require_auth)):
    query = db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id)
    if strategy_type:
        query = query.filter(StrategyConfig.strategy_type == strategy_type)
    cfg = query.order_by(StrategyConfig.id.desc()).first()
    if not cfg:
        # Return a default initial config if none exists for this user
        now = datetime.utcnow()
        is_destiny = strategy_type == "DESTINY"
        return StrategyConfigResponse(
            id=0,
            r1=24100 if is_destiny else 23170, r2=24200 if is_destiny else 23220, r3=24300 if is_destiny else 23250,
            s1=23900 if is_destiny else 23070, s2=23800 if is_destiny else 23025, s3=23700 if is_destiny else 22950,
            lot_size=65,
            target_points=30,
            sl_points=10,
            paper_trade=True,
            squareoff_time="15:20",
            strategy_type=strategy_type or "PYRAMID",
            is_active=False,
            created_at=now,
            updated_at=now
        )
    return cfg


@router.get("/strategy/history", response_model=list[StrategyConfigResponse])
def get_strategy_config_history(
    from_date: str = None,
    to_date: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth)
):
    query = db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id)
    if from_date:
        query = query.filter(StrategyConfig.created_at >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(StrategyConfig.created_at <= f"{to_date} 23:59:59")
    
    return query.order_by(StrategyConfig.created_at.desc()).limit(limit).all()


@router.post("/strategy", response_model=StrategyConfigResponse)
def create_strategy_config(payload: StrategyConfigCreate, db: Session = Depends(get_db), user: User = Depends(require_auth)):
    # Deactivate existing configs for this user
    db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id).update({"is_active": False})

    cfg = StrategyConfig(
        user_id=user.id,
        strategy_type=payload.strategy_type or "PYRAMID",
        r1=payload.r1, r2=payload.r2, r3=payload.r3,
        s1=payload.s1, s2=payload.s2, s3=payload.s3,
        lot_size=payload.lot_size,
        target_points=payload.target_points,
        sl_points=payload.sl_points,
        paper_trade=payload.paper_trade,
        squareoff_time=payload.squareoff_time,
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    # Force re-instantiate / update user engine instance in EngineManager based on strategy_type
    if user.id in engine_manager._engines:
        old_engine = engine_manager._engines[user.id]
        if old_engine.is_running:
            old_engine.stop()
        del engine_manager._engines[user.id]

    user_engine = engine_manager.get_engine(user.id)
    if hasattr(user_engine, 'load_config'):
        user_engine.load_config({
            "r1": float(cfg.r1), "r2": float(cfg.r2), "r3": float(cfg.r3),
            "s1": float(cfg.s1), "s2": float(cfg.s2), "s3": float(cfg.s3),
            "lot_size": cfg.lot_size,
            "target_points": float(cfg.target_points),
            "sl_points": float(cfg.sl_points),
            "paper_trade": cfg.paper_trade,
            "squareoff_time": cfg.squareoff_time,
            "strategy_type": cfg.strategy_type,
        })
    elif hasattr(user_engine, '_load_config'):
        user_engine._load_config()

    # Update active KiteService ticker callbacks to new engine
    try:
        from app.services.kite_service import get_user_kite_service
        ks = get_user_kite_service(user.id)
        if ks._ticker_running:
            ks.update_callbacks(user_engine.on_nifty_tick, user_engine.on_option_tick)
    except Exception as e:
        logger.warning(f"Failed to update KiteTicker callbacks for user {user.id}: {e}")

    # Dynamic log window config update
    try:
        from app.core.logging_config import update_logging_window
        update_logging_window()
    except Exception as ex:
        logger.error(f"Error updating logging window on config change: {ex}")

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

    # Encrypt credentials for Zerodha programmatic auto-login
    if payload.provider == "zerodha" and payload.extra_config:
        username = payload.extra_config.get("username")
        password = payload.extra_config.get("password")
        totp_secret = payload.extra_config.get("totp_secret")
        
        extra = dict(existing.extra_config or {}) if existing else {}
        if username is not None:
            extra["username"] = username
        if password:
            extra["password_encrypted"] = encrypt(password)
        if totp_secret:
            extra["totp_secret_encrypted"] = encrypt(totp_secret)
        
        extra.pop("password", None)
        extra.pop("totp_secret", None)
        payload.extra_config = extra

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
    elif payload.provider == "whatsapp":
        from app.services.whatsapp import get_user_whatsapp_service
        get_user_whatsapp_service(user.id).load_from_db()
    elif payload.provider in ("openai", "anthropic", "gemini"):
        existing.is_active = True
        other_providers = [p for p in ("openai", "anthropic", "gemini") if p != payload.provider]
        db.query(ApiConfig).filter(
            ApiConfig.user_id == user.id,
            ApiConfig.provider.in_(other_providers)
        ).update({ApiConfig.is_active: False}, synchronize_session=False)
        db.commit()
        from app.services.ai_service import get_user_ai_service
        get_user_ai_service(user.id).load_from_db()

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
            
        extra_config_filtered = dict(cfg.extra_config or {}) if cfg.extra_config else {}
        if cfg.provider == "zerodha":
            if "password_encrypted" in extra_config_filtered:
                extra_config_filtered["has_password"] = True
                extra_config_filtered.pop("password_encrypted", None)
            if "totp_secret_encrypted" in extra_config_filtered:
                extra_config_filtered["has_totp"] = True
                extra_config_filtered.pop("totp_secret_encrypted", None)
                
        result.append(ApiConfigResponse(
            provider=cfg.provider,
            api_key_masked=masked,
            is_active=cfg.is_active,
            extra_config=extra_config_filtered if cfg.extra_config else None,
        ))
    return result
