import razorpay
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import ApiConfig
from app.services.encryption import decrypt
from loguru import logger
import hmac
import hashlib


def get_razorpay_client(db: Session = None):
    """
    Retrieves Razorpay client dynamically from DB (ApiConfig where provider='razorpay') 
    or falls back to environment variables.
    """
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET

    if db:
        config = db.query(ApiConfig).filter(
            ApiConfig.provider == "razorpay",
            ApiConfig.is_active == True
        ).first()
        if config:
            if config.api_key_encrypted:
                try:
                    key_id = decrypt(config.api_key_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt Razorpay Key ID: {e}")
            if config.api_secret_encrypted:
                try:
                    key_secret = decrypt(config.api_secret_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt Razorpay Key Secret: {e}")

    if not key_id or not key_secret:
        return None, key_id

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        return client, key_id
    except Exception as e:
        logger.error(f"Failed to initialize Razorpay client: {e}")
        return None, key_id


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, key_secret: str) -> bool:
    """
    Verifies HMAC SHA256 payment signature returned by Razorpay Checkout.
    """
    if not key_secret:
        return False
    try:
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        generated_signature = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_signature, razorpay_signature)
    except Exception as e:
        logger.error(f"Razorpay signature verification exception: {e}")
        return False


def verify_webhook_signature(body: bytes, signature: str, webhook_secret: str) -> bool:
    """
    Verifies Razorpay Webhook signature.
    """
    if not webhook_secret:
        return False
    try:
        generated_signature = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_signature, signature)
    except Exception as e:
        logger.error(f"Webhook signature verification exception: {e}")
        return False
