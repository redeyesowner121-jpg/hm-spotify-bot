"""
Security module — Fernet encryption, credential masking, authorization guard.
"""

import functools
import logging
from cryptography.fernet import Fernet, InvalidToken
from config import settings

logger = logging.getLogger(__name__)


class CredentialManager:
    """Encrypts and decrypts sensitive data using Fernet symmetric encryption."""

    def __init__(self, key: str | None = None):
        key = key or settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("Encryption key not configured")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string, returns base64-encoded ciphertext."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string back to plaintext."""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise ValueError("Decryption failed — invalid key or corrupted data")

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (for initial setup)."""
        return Fernet.generate_key().decode("utf-8")


def mask_password(password: str) -> str:
    """Mask a password for display: shows first and last char only."""
    if not password:
        return "***"
    if len(password) <= 3:
        return "*" * len(password)
    return password[0] + "*" * (len(password) - 2) + password[-1]


def mask_email(email: str) -> str:
    """Mask an email for display: s***e@domain.com."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def extract_name_from_email(email: str) -> str:
    """Extract display name from email prefix (text before @)."""
    if not email or "@" not in email:
        return "User"
    local = email.split("@", 1)[0]
    # Replace dots, underscores, hyphens with spaces and title-case
    name = local.replace(".", " ").replace("_", " ").replace("-", " ")
    return name.strip().title() or "User"


def authorized_only(func):
    """Decorator: permits all users (public / no restrictions)."""

    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        return await func(update, context, *args, **kwargs)

    return wrapper
