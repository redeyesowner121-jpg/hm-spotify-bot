"""
Start handler — /start command and main menu display.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from security import authorized_only
from handlers.common import get_main_menu_keyboard, CB_MAIN_MENU

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🤖 *H&M + Spotify Automation Bot*\n\n"
    "Welcome! This bot helps you manage your personal H&M and Spotify accounts.\n\n"
    "🔒 *Security:*\n"
    "• Only your authorized account can use this bot\n"
    "• Passwords are encrypted and never stored in plain text\n"
    "• CAPTCHA/security challenges are never bypassed\n"
    "• Only official website interfaces are used\n\n"
    "Choose an action below:"
)


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command — show the main menu."""
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


@authorized_only
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'Back to Menu' button — redisplay the main menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


def get_start_handlers() -> list:
    """Return handlers for /start and main menu navigation."""
    return [
        CommandHandler("start", start_command),
        CallbackQueryHandler(main_menu_callback, pattern=f"^{CB_MAIN_MENU}$"),
    ]
