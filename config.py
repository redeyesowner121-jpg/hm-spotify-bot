"""
Configuration module — loads all settings from environment variables.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Telegram
        self.TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.AUTHORIZED_USER_IDS: list[int] = self._parse_user_ids(
            os.getenv("AUTHORIZED_USER_IDS", "")
        )

        # Security
        self.ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

        # Database
        self.DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot.db")

        # Browser
        self.BROWSER_HEADLESS: bool = (
            os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        )

        # H&M
        self.HM_BASE_URL: str = os.getenv("HM_BASE_URL", "https://www2.hm.com")

        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @staticmethod
    def _parse_user_ids(raw: str) -> list[int]:
        ids = []
        for uid in raw.split(","):
            uid = uid.strip()
            if uid:
                try:
                    ids.append(int(uid))
                except ValueError:
                    logger.warning(f"Invalid user ID ignored: {uid}")
        return ids

    def validate(self):
        """Validate that all required settings are present."""
        errors = []
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if not self.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY is required — generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        if errors:
            raise ValueError(
                "❌ Configuration errors:\n  • " + "\n  • ".join(errors)
            )

    def __repr__(self):
        return (
            f"Settings(bot_token={'SET' if self.TELEGRAM_BOT_TOKEN else 'MISSING'}, "
            f"users={self.AUTHORIZED_USER_IDS}, "
            f"db={self.DATABASE_PATH}, "
            f"headless={self.BROWSER_HEADLESS})"
        )


# Global singleton
settings = Settings()
