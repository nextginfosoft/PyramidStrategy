import os
from typing import Optional
from loguru import logger
import httpx

class WhatsAppService:
    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self._enabled = False
        self._provider_type = "meta"  # "meta" or "twilio"
        
        # Meta config
        self._access_token: Optional[str] = None
        self._phone_number_id: Optional[str] = None
        self._recipient_phone: Optional[str] = None
        
        # Twilio config
        self._twilio_sid: Optional[str] = None
        self._twilio_auth_token: Optional[str] = None
        self._twilio_from: Optional[str] = None
        self._twilio_to: Optional[str] = None

    def configure_meta(self, access_token: str, phone_number_id: str, recipient_phone: str):
        self._provider_type = "meta"
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._recipient_phone = recipient_phone
        self._enabled = bool(access_token and phone_number_id and recipient_phone)
        logger.info(f"WhatsAppService (Meta) configured for User {self.user_id}: enabled={self._enabled}")

    def configure_twilio(self, twilio_sid: str, twilio_auth_token: str, from_phone: str, to_phone: str):
        self._provider_type = "twilio"
        self._twilio_sid = twilio_sid
        self._twilio_auth_token = twilio_auth_token
        self._twilio_from = from_phone
        self._twilio_to = to_phone
        self._enabled = bool(twilio_sid and twilio_auth_token and from_phone and to_phone)
        logger.info(f"WhatsAppService (Twilio) configured for User {self.user_id}: enabled={self._enabled}")

    def load_from_db(self):
        """Load WhatsApp credentials from DB."""
        try:
            from app.db.database import SessionLocal
            from app.models.models import ApiConfig
            from app.services.encryption import decrypt

            with SessionLocal() as db:
                row = db.query(ApiConfig).filter(
                    ApiConfig.user_id == self.user_id,
                    ApiConfig.provider == "whatsapp",
                    ApiConfig.is_active == True,
                ).first()
                if row:
                    extra = row.extra_config or {}
                    provider_type = extra.get("provider_type", "meta")
                    
                    if provider_type == "meta" and row.api_key_encrypted:
                        token = decrypt(row.api_key_encrypted)
                        phone_number_id = extra.get("phone_number_id", "")
                        recipient_phone = extra.get("recipient_phone", "")
                        if token and phone_number_id and recipient_phone:
                            self.configure_meta(token, phone_number_id, recipient_phone)
                            return
                    elif provider_type == "twilio" and row.api_key_encrypted and row.api_secret_encrypted:
                        sid = decrypt(row.api_key_encrypted)
                        auth_token = decrypt(row.api_secret_encrypted)
                        from_phone = extra.get("from_phone", "")
                        to_phone = extra.get("to_phone", "")
                        if sid and auth_token and from_phone and to_phone:
                            self.configure_twilio(sid, auth_token, from_phone, to_phone)
                            return
                            
            logger.info(f"User {self.user_id}: WhatsApp not configured — notifications disabled")
            self._enabled = False
        except Exception as e:
            logger.warning(f"User {self.user_id}: WhatsApp config load failed: {e}")
            self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    async def test_connection(self) -> tuple[bool, str]:
        """Send a test message to WhatsApp. Returns (success, message)."""
        if not self._enabled:
            return False, "WhatsApp not configured — save credentials in Settings first"
        try:
            success = await self.send_message("✅ *PyramidStrategy* — WhatsApp connected successfully!")
            if success:
                return True, "Test WhatsApp message sent successfully"
            else:
                return False, "Failed to send WhatsApp message. Check logs for details."
        except Exception as e:
            return False, f"Failed: {str(e)}"

    async def send_message(self, text: str) -> bool:
        """Send a text message to WhatsApp."""
        if not self._enabled:
            logger.debug(f"WhatsApp disabled for User {self.user_id}. Message: {text[:50]}...")
            return False
            
        if self._provider_type == "meta":
            return await self._send_meta_message(text)
        else:
            return await self._send_twilio_message(text)

    async def send_document(self, file_path: str, caption: str) -> bool:
        """Send a document (PDF) to WhatsApp."""
        if not self._enabled:
            logger.debug(f"WhatsApp disabled for User {self.user_id}. Skip sending document {file_path}")
            return False
            
        if self._provider_type == "meta":
            return await self._send_meta_document(file_path, caption)
        else:
            # Twilio media messages require a public HTTPS URL. Since we are running locally, 
            # we send a text briefing and log the document send.
            filename = os.path.basename(file_path)
            briefing = f"📎 *PDF Report Generated*: {filename}\nCaption: {caption}\n(Note: Twilio media delivery requires a public URL. File saved locally at: {file_path})"
            logger.info(f"[Twilio Mock Media] Sending document notification: {file_path}")
            return await self.send_message(briefing)

    # ── Meta Implementation ───────────────────────────────────────────────────

    async def _send_meta_message(self, text: str) -> bool:
        if not self._recipient_phone:
            return False
        recipients = [r.strip() for r in self._recipient_phone.split(",") if r.strip()]
        if not recipients:
            return False

        url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
        success = True
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for recipient in recipients:
                    payload = {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": recipient,
                        "type": "text",
                        "text": {
                            "body": text
                        }
                    }
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        logger.info(f"User {self.user_id}: WhatsApp Meta message sent successfully to {recipient}")
                    else:
                        logger.warning(f"User {self.user_id}: WhatsApp Meta send failed to {recipient}: {resp.status_code} {resp.text}")
                        success = False
        except Exception as e:
            logger.error(f"User {self.user_id}: WhatsApp Meta failed: {e}")
            success = False
        return success

    async def _send_meta_document(self, file_path: str, caption: str) -> bool:
        if not self._recipient_phone:
            return False
        recipients = [r.strip() for r in self._recipient_phone.split(",") if r.strip()]
        if not recipients:
            return False

        # Step 1: Upload Media to get Media ID
        upload_url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {self._access_token}"
        }
        filename = os.path.basename(file_path)
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                with open(file_path, "rb") as f:
                    files = {
                        "file": (filename, f, "application/pdf")
                    }
                    data = {
                        "messaging_product": "whatsapp",
                        "type": "application/pdf"
                    }
                    resp = await client.post(upload_url, headers=headers, data=data, files=files)
                    
                if resp.status_code != 200:
                    logger.warning(f"User {self.user_id}: WhatsApp Meta media upload failed: {resp.status_code} {resp.text}")
                    return False
                    
                media_id = resp.json().get("id")
                if not media_id:
                    logger.warning("User {self.user_id}: WhatsApp Meta upload returned success but no media ID")
                    return False
                    
                # Step 2: Send Message referencing the Media ID
                msg_url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}/messages"
                msg_headers = {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json"
                }
                success = True
                for recipient in recipients:
                    msg_payload = {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": recipient,
                        "type": "document",
                        "document": {
                            "id": media_id,
                            "caption": caption,
                            "filename": filename
                        }
                    }
                    resp = await client.post(msg_url, json=msg_payload, headers=msg_headers)
                    if resp.status_code == 200:
                        logger.info(f"User {self.user_id}: WhatsApp Meta document sent successfully to {recipient}")
                    else:
                        logger.warning(f"User {self.user_id}: WhatsApp Meta document send failed to {recipient}: {resp.status_code} {resp.text}")
                        success = False
                return success
        except Exception as e:
            logger.error(f"User {self.user_id}: WhatsApp Meta document send exception: {e}")
            return False

    # ── Twilio Implementation ─────────────────────────────────────────────────

    async def _send_twilio_message(self, text: str) -> bool:
        if not self._twilio_to:
            return False
        recipients = [r.strip() for r in self._twilio_to.split(",") if r.strip()]
        if not recipients:
            return False
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._twilio_sid}/Messages.json"
        auth = (self._twilio_sid, self._twilio_auth_token)
        success = True
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for recipient in recipients:
                    clean_recipient = recipient.replace("whatsapp:", "").strip()
                    data = {
                        "To": f"whatsapp:{clean_recipient}",
                        "From": f"whatsapp:{self._twilio_from}",
                        "Body": text
                    }
                    resp = await client.post(url, auth=auth, data=data)
                    if resp.status_code in (200, 201):
                        logger.info(f"User {self.user_id}: WhatsApp Twilio message sent successfully to {clean_recipient}")
                    else:
                        logger.warning(f"User {self.user_id}: WhatsApp Twilio send failed to {clean_recipient}: {resp.status_code} {resp.text}")
                        success = False
        except Exception as e:
            logger.error(f"User {self.user_id}: WhatsApp Twilio failed: {e}")
            success = False
        return success

# Global user instance cache for WhatsApp
_whatsapp_instances: dict[int, WhatsAppService] = {}

def get_user_whatsapp_service(user_id: int) -> WhatsAppService:
    if user_id not in _whatsapp_instances:
        _whatsapp_instances[user_id] = WhatsAppService(user_id)
    return _whatsapp_instances[user_id]
