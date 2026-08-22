import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import ApiConfig
from app.services.encryption import decrypt
from loguru import logger

SENDFOX_BASE_URL = "https://api.sendfox.com"


def get_sendfox_config(db: Session = None):
    """
    Retrieves SendFox API credentials dynamically from DB (ApiConfig where provider='sendfox')
    or falls back to environment variables.
    """
    api_key = settings.SENDFOX_API_KEY
    welcome_list_id = settings.SENDFOX_WELCOME_LIST_ID
    pro_list_id = settings.SENDFOX_PRO_LIST_ID

    if db:
        config = db.query(ApiConfig).filter(
            ApiConfig.provider == "sendfox",
            ApiConfig.is_active == True
        ).first()
        if config:
            if config.api_key_encrypted:
                try:
                    api_key = decrypt(config.api_key_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt SendFox API Key: {e}")
            if config.extra_config:
                welcome_list_id = config.extra_config.get("welcome_list_id", welcome_list_id)
                pro_list_id = config.extra_config.get("pro_list_id", pro_list_id)

    return api_key, welcome_list_id, pro_list_id


async def add_sendfox_contact(email: str, first_name: str = "", list_ids: list = None, db: Session = None):
    """
    Asynchronously adds or updates a contact in SendFox and subscribes them to specified lists.
    Runs non-blocking in FastAPI background tasks.
    """
    if not email or "@" not in email:
        return False

    api_key, welcome_list_id, pro_list_id = get_sendfox_config(db)
    if not api_key:
        logger.debug("SendFox API Key not configured. Skipping email marketing contact sync.")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Default to welcome_list_id if no specific list_ids provided
    target_lists = []
    if list_ids:
        target_lists = list_ids
    elif welcome_list_id:
        target_lists = [welcome_list_id]

    payload = {
        "email": email,
        "first_name": first_name or email.split("@")[0],
    }
    if target_lists:
        payload["lists"] = target_lists

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{SENDFOX_BASE_URL}/contacts", json=payload, headers=headers)
            if response.status_code in (200, 201):
                logger.info(f"SendFox contact successfully added/updated: {email} (Lists: {target_lists})")
                return True
            else:
                logger.warning(f"SendFox API returned status {response.status_code}: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Exception while syncing contact to SendFox: {e}")
        return False
