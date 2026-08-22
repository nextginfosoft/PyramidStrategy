from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from loguru import logger

from app.db.database import get_db
from app.models.models import User, SubscriptionPlan, UserSubscription, PaymentTransaction, ApiConfig
from app.api.routes.session import require_auth, require_admin
from app.services.payment_service import get_razorpay_client, verify_payment_signature, verify_webhook_signature
from app.services.encryption import encrypt, decrypt

router = APIRouter(prefix="/payments", tags=["payments"])


# ── Schemas ──────────────────────────────────────────────────────────────────
class PlanResponse(BaseModel):
    id: int
    plan_code: str
    name: str
    description: Optional[str]
    billing_period: str
    interval_count: int
    price: float
    discount_percentage: int
    is_active: bool


class CreateOrderRequest(BaseModel):
    plan_code: str


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    plan_code: str
    plan_name: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_code: str


class RazorpayConfigUpdate(BaseModel):
    key_id: str
    key_secret: str
    webhook_secret: Optional[str] = ""
    is_active: bool = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=List[PlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Fetch active subscription plans."""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    return [
        PlanResponse(
            id=p.id,
            plan_code=p.plan_code,
            name=p.name,
            description=p.description,
            billing_period=p.billing_period,
            interval_count=p.interval_count,
            price=float(p.price),
            discount_percentage=p.discount_percentage,
            is_active=p.is_active
        ) for p in plans
    ]


@router.get("/my-status")
def get_user_subscription_status(
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Fetch current logged-in user's subscription state."""
    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "ACTIVE"
    ).order_by(UserSubscription.current_end.desc()).first()

    return {
        "user_id": user.id,
        "subscription_tier": user.subscription_tier or "BASIC",
        "subscription_status": user.subscription_status or "INACTIVE",
        "subscription_ends_at": user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
        "active_subscription": {
            "id": active_sub.id if active_sub else None,
            "razorpay_subscription_id": active_sub.razorpay_subscription_id if active_sub else None,
            "current_start": active_sub.current_start.isoformat() if active_sub and active_sub.current_start else None,
            "current_end": active_sub.current_end.isoformat() if active_sub and active_sub.current_end else None,
        } if active_sub else None
    }


@router.post("/create-order", response_model=CreateOrderResponse)
def create_payment_order(
    req: CreateOrderRequest,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Create a Razorpay Order for a subscription plan."""
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_code == req.plan_code,
        SubscriptionPlan.is_active == True
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")

    client, key_id = get_razorpay_client(db)
    if not client or not key_id:
        raise HTTPException(
            status_code=400,
            detail="Razorpay API credentials not configured. Please contact support/admin."
        )

    # Razorpay amount is in paise (₹1 = 100 paise)
    amount_in_paise = int(float(plan.price) * 100)

    order_payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"rcpt_u{user.id}_p{plan.id}_{int(datetime.now().timestamp())}",
        "notes": {
            "user_id": str(user.id),
            "username": user.username,
            "plan_code": plan.plan_code
        }
    }

    try:
        rzp_order = client.order.create(data=order_payload)
        order_id = rzp_order.get("id")

        # Record pending transaction in DB
        txn = PaymentTransaction(
            user_id=user.id,
            razorpay_order_id=order_id,
            amount=plan.price,
            currency="INR",
            status="PENDING"
        )
        db.add(txn)
        db.commit()

        return CreateOrderResponse(
            order_id=order_id,
            amount=amount_in_paise,
            currency="INR",
            key_id=key_id,
            plan_code=plan.plan_code,
            plan_name=plan.name
        )
    except Exception as e:
        logger.error(f"Failed to create Razorpay order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment order: {str(e)}")


@router.post("/verify")
def verify_payment(
    req: VerifyPaymentRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Verify payment signature from Razorpay modal and activate user Pro plan."""
    _, key_id = get_razorpay_client(db)
    
    # Retrieve key_secret from DB or config
    config = db.query(ApiConfig).filter(
        ApiConfig.provider == "razorpay",
        ApiConfig.is_active == True
    ).first()
    
    key_secret = None
    if config and config.api_secret_encrypted:
        try:
            key_secret = decrypt(config.api_secret_encrypted)
        except Exception:
            pass
    
    from app.config import settings
    if not key_secret:
        key_secret = settings.RAZORPAY_KEY_SECRET

    if not key_secret:
        raise HTTPException(status_code=400, detail="Razorpay secret not configured")

    is_valid = verify_payment_signature(
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=req.razorpay_signature,
        key_secret=key_secret
    )

    if not is_valid:
        # Mark transaction failed
        txn = db.query(PaymentTransaction).filter(
            PaymentTransaction.razorpay_order_id == req.razorpay_order_id
        ).first()
        if txn:
            txn.status = "FAILED"
            txn.error_message = "Invalid payment signature"
            db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature. Payment verification failed.")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == req.plan_code).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Compute duration
    now = datetime.now(timezone.utc)
    if plan.billing_period == "monthly":
        days = 30 * plan.interval_count
    elif plan.billing_period == "yearly":
        days = 365 * plan.interval_count
    else:
        days = 30

    # Extend current end date if user already active, else from now
    if user.subscription_ends_at and user.subscription_ends_at > now:
        new_end_date = user.subscription_ends_at + timedelta(days=days)
    else:
        new_end_date = now + timedelta(days=days)

    # Update User status
    user.subscription_tier = "PRO"
    user.subscription_status = "ACTIVE"
    user.subscription_ends_at = new_end_date

    # Record UserSubscription
    user_sub = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status="ACTIVE",
        current_start=now,
        current_end=new_end_date
    )
    db.add(user_sub)
    db.flush()

    # Update PaymentTransaction
    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.razorpay_order_id == req.razorpay_order_id
    ).first()
    if txn:
        txn.razorpay_payment_id = req.razorpay_payment_id
        txn.razorpay_signature = req.razorpay_signature
        txn.subscription_id = user_sub.id
        txn.status = "CAPTURED"
    else:
        txn = PaymentTransaction(
            user_id=user.id,
            subscription_id=user_sub.id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_order_id=req.razorpay_order_id,
            razorpay_signature=req.razorpay_signature,
            amount=plan.price,
            status="CAPTURED"
        )
        db.add(txn)

    db.commit()

    logger.info(f"🎉 User {user.id} ({user.username}) successfully upgraded to PRO plan ({plan.plan_code}) until {new_end_date}")

    # SendFox Email Marketing Automation Sync (Add user to Pro Customer List)
    if "@" in user.username:
        try:
            from app.services.sendfox_service import add_sendfox_contact, get_sendfox_config
            _, _, pro_list_id = get_sendfox_config(db)
            target_lists = [pro_list_id] if pro_list_id else None
            background_tasks.add_task(add_sendfox_contact, user.username, user.username.split("@")[0], target_lists, db)
        except Exception as e:
            logger.warning(f"Failed to queue SendFox Pro contact sync task: {e}")

    return {
        "status": "success",
        "message": f"Successfully subscribed to {plan.name}!",
        "subscription_tier": user.subscription_tier,
        "subscription_status": user.subscription_status,
        "subscription_ends_at": new_end_date.isoformat()
    }


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Razorpay Webhook receiver for background payment events."""
    body = await request.body()
    
    # Fetch webhook secret
    config = db.query(ApiConfig).filter(
        ApiConfig.provider == "razorpay",
        ApiConfig.is_active == True
    ).first()
    
    webhook_secret = None
    if config and config.extra_config:
        try:
            webhook_secret_enc = config.extra_config.get("webhook_secret_encrypted")
            if webhook_secret_enc:
                webhook_secret = decrypt(webhook_secret_enc)
        except Exception:
            pass

    from app.config import settings
    if not webhook_secret:
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    if webhook_secret and x_razorpay_signature:
        if not verify_webhook_signature(body, x_razorpay_signature, webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_data = await request.json()
    event_type = event_data.get("event")
    logger.info(f"Received Razorpay Webhook Event: {event_type}")

    # Process events like payment.captured
    if event_type == "payment.captured":
        payload = event_data.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payload.get("order_id")
        payment_id = payload.get("id")
        
        txn = db.query(PaymentTransaction).filter(PaymentTransaction.razorpay_order_id == order_id).first()
        if txn:
            txn.razorpay_payment_id = payment_id
            txn.status = "CAPTURED"
            db.commit()

    return {"status": "ok"}


# ── Admin Gateway Config Endpoints ──────────────────────────────────────────

@router.get("/admin/config")
def get_razorpay_admin_config(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Fetch Razorpay API key configuration for Admin Panel."""
    config = db.query(ApiConfig).filter(ApiConfig.provider == "razorpay").first()
    key_id = ""
    is_active = True
    has_secret = False
    has_webhook = False

    if config:
        is_active = config.is_active
        if config.api_key_encrypted:
            try:
                key_id = decrypt(config.api_key_encrypted)
            except Exception:
                pass
        has_secret = bool(config.api_secret_encrypted)
        has_webhook = bool(config.extra_config and config.extra_config.get("webhook_secret_encrypted"))
    else:
        from app.config import settings
        key_id = settings.RAZORPAY_KEY_ID or ""
        has_secret = bool(settings.RAZORPAY_KEY_SECRET)
        has_webhook = bool(settings.RAZORPAY_WEBHOOK_SECRET)

    return {
        "key_id": key_id,
        "has_key_secret": has_secret,
        "has_webhook_secret": has_webhook,
        "is_active": is_active
    }


@router.post("/admin/config")
def update_razorpay_admin_config(
    req: RazorpayConfigUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Save/Update Razorpay API Key ID & Secret dynamically from Admin Panel."""
    config = db.query(ApiConfig).filter(ApiConfig.provider == "razorpay").first()
    
    extra = {}
    if config and config.extra_config:
        extra = dict(config.extra_config)

    if req.webhook_secret:
        extra["webhook_secret_encrypted"] = encrypt(req.webhook_secret)

    if not config:
        config = ApiConfig(
            user_id=admin.id,
            provider="razorpay",
            api_key_encrypted=encrypt(req.key_id),
            api_secret_encrypted=encrypt(req.key_secret),
            extra_config=extra,
            is_active=req.is_active
        )
        db.add(config)
    else:
        config.api_key_encrypted = encrypt(req.key_id)
        if req.key_secret and req.key_secret != "******":
            config.api_secret_encrypted = encrypt(req.key_secret)
        config.extra_config = extra
        config.is_active = req.is_active

    db.commit()
    logger.info(f"Admin {admin.username} updated Razorpay payment gateway credentials.")
    return {"status": "success", "message": "Razorpay configuration updated"}


# ── SendFox Admin Config Endpoints ──────────────────────────────────────────────
class SendFoxConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    welcome_list_id: Optional[str] = None
    pro_list_id: Optional[str] = None
    is_active: bool = True


@router.get("/admin/sendfox")
def get_sendfox_admin_config(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Fetch SendFox API key configuration for Admin Panel."""
    config = db.query(ApiConfig).filter(ApiConfig.provider == "sendfox").first()
    has_api_key = False
    welcome_list_id = ""
    pro_list_id = ""
    is_active = True

    if config:
        is_active = config.is_active
        has_api_key = bool(config.api_key_encrypted)
        if config.extra_config:
            welcome_list_id = config.extra_config.get("welcome_list_id", "")
            pro_list_id = config.extra_config.get("pro_list_id", "")
    else:
        from app.config import settings
        has_api_key = bool(settings.SENDFOX_API_KEY)
        welcome_list_id = settings.SENDFOX_WELCOME_LIST_ID or ""
        pro_list_id = settings.SENDFOX_PRO_LIST_ID or ""

    return {
        "has_api_key": has_api_key,
        "welcome_list_id": welcome_list_id,
        "pro_list_id": pro_list_id,
        "is_active": is_active
    }


@router.post("/admin/sendfox")
def update_sendfox_admin_config(
    req: SendFoxConfigUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Save/Update SendFox API Key & List IDs dynamically from Admin Panel."""
    config = db.query(ApiConfig).filter(ApiConfig.provider == "sendfox").first()
    
    extra = {}
    if config and config.extra_config:
        extra = dict(config.extra_config)

    if req.welcome_list_id is not None:
        extra["welcome_list_id"] = req.welcome_list_id
    if req.pro_list_id is not None:
        extra["pro_list_id"] = req.pro_list_id

    if not config:
        config = ApiConfig(
            user_id=admin.id,
            provider="sendfox",
            api_key_encrypted=encrypt(req.api_key) if req.api_key else None,
            extra_config=extra,
            is_active=req.is_active
        )
        db.add(config)
    else:
        if req.api_key:
            config.api_key_encrypted = encrypt(req.api_key)
        config.extra_config = extra
        config.is_active = req.is_active

    db.commit()
    logger.info("SendFox admin configuration updated dynamically by admin")
    return {"status": "success", "message": "SendFox configuration updated"}
