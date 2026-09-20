"""
bot.py — Main entry point for the H&M + Spotify Telegram Automation Bot.

Initializes all components, registers handlers, and starts polling.
"""

import logging
import asyncio
import sys
from telegram.ext import Application

from config import settings
from security import CredentialManager
from database import Database
from browser import BrowserManager
from hm_client import HMClient
from spotify_client import SpotifyClient

from handlers.start import get_start_handlers
from handlers.hm_handlers import get_hm_conversation_handler
from handlers.spotify_handlers import (
    get_spotify_create_handler,
    get_code_retrieval_handler,
    get_redeem_handler,
)
from handlers.session_handlers import get_session_handlers


def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce noise from third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


async def post_init(application: Application):
    """Initialize shared resources after the application is built."""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Initializing bot resources...")

    # Validate configuration
    settings.validate()

    # Initialize credential manager
    cred = CredentialManager()
    application.bot_data["cred"] = cred
    logger.info("🔐 Credential manager initialized")

    # Initialize database
    db = Database(settings.DATABASE_PATH)
    await db.initialize()
    application.bot_data["db"] = db
    logger.info("💾 Database initialized")

    # Initialize browser manager
    browser = BrowserManager(
        headless=settings.BROWSER_HEADLESS,
        db=db,
        cred_mgr=cred,
    )
    await browser.initialize()
    application.bot_data["browser"] = browser
    logger.info("🌐 Browser initialized")

    # Initialize clients
    hm_client = HMClient(browser, db, cred)
    spotify_client = SpotifyClient(browser, db, cred)
    application.bot_data["hm_client"] = hm_client
    application.bot_data["spotify_client"] = spotify_client
    logger.info("✅ All clients initialized")

    logger.info(f"🤖 Bot ready! Authorized users: {settings.AUTHORIZED_USER_IDS}")


async def post_shutdown(application: Application):
    """Clean up resources on shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("🛑 Shutting down...")

    browser = application.bot_data.get("browser")
    if browser:
        await browser.close()

    db = application.bot_data.get("db")
    if db:
        await db.close()

    logger.info("👋 Shutdown complete")


def main():
    """Build and run the Telegram bot application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("═" * 50)
    logger.info("  H&M + Spotify Telegram Automation Bot")
    logger.info("═" * 50)
    logger.info(f"Config: {settings}")

    # Build the application
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ── Register handlers ─────────────────────────────────
    # Order matters: ConversationHandlers first, then plain callbacks

    # Conversation handlers (multi-step flows)
    application.add_handler(get_hm_conversation_handler())
    application.add_handler(get_spotify_create_handler())
    application.add_handler(get_code_retrieval_handler())
    application.add_handler(get_redeem_handler())

    # Start and menu handlers
    for handler in get_start_handlers():
        application.add_handler(handler)

    # Session handlers (single-step callbacks)
    for handler in get_session_handlers():
        application.add_handler(handler)

    # ── Start polling ─────────────────────────────────────
    logger.info("🏃 Starting bot polling...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
