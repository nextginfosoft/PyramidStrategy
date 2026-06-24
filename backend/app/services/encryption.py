"""
AES-256 Encryption for API keys stored in DB.
Uses cryptography library (Fernet = AES-128-CBC + HMAC).
For AES-256, we use AES-GCM directly.
"""

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings


def _get_key() -> bytes:
    """Get 32-byte encryption key."""
    key = settings.ENCRYPTION_KEY.encode("latin-1")[:32]
    return key.ljust(32, b"\0")


def encrypt(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Prepend nonce to ciphertext for storage
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded ciphertext string."""
    if not ciphertext_b64:
        return ""
    from loguru import logger
    try:
        key = _get_key()
        aesgcm = AESGCM(key)
        combined = base64.b64decode(ciphertext_b64.encode("utf-8"))
        nonce = combined[:12]
        ciphertext = combined[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        logger.error(f"Decryption failed (possibly invalid signature, mismatched key, or corruption): {e}")
        return ""


def mask_key(key: str) -> str:
    """Return masked version for display: show only last 4 chars."""
    if not key or len(key) < 8:
        return "****"
    return f"{'*' * (len(key) - 4)}{key[-4:]}"
