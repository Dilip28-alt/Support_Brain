"""
Encryption utilities for Gmail tokens using Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet
from app.config import get_settings
import base64
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    # Ensure it is a valid 32-byte URL-safe base64 key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # If the key is a raw 32-byte string, encode it
        encoded = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b"\0"))
        return Fernet(encoded)


def encrypt_token(token: str) -> str:
    """Encrypt a plain-text OAuth token for safe database storage."""
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored OAuth token."""
    f = _get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()
