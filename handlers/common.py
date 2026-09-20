"""
Common handler utilities — shared keyboard builders, progress senders,
error formatters, and the authorization decorator for Telegram handlers.
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from security import authorized_only, mask_email, mask_password  # noqa: F401

logger = logging.getLogger(__name__)

# ── Callback Data Constants ───────────────────────────────

# Main menu
CB_HM_CREATE = "hm_create"
CB_SPOTIFY_CREATE = "spotify_create"
CB_GET_CODE = "get_spotify_code"
CB_REDEEM = "redeem_spotify_code"
CB_STATUS = "account_status"
CB_SESSION_MGR = "session_management"
CB_LOGOUT = "logout"

# Region selection
CB_REGION_IN = "region_en_in"
CB_REGION_GB = "region_en_gb"

# Confirmations
CB_CONFIRM = "confirm_yes"
CB_CANCEL = "confirm_no"

# Back to menu
CB_MAIN_MENU = "main_menu"


# ── Keyboards ─────────────────────────────────────────────

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Create H&M Account", callback_data=CB_HM_CREATE)],
        [InlineKeyboardButton("🎵 Create Spotify Account", callback_data=CB_SPOTIFY_CREATE)],
        [InlineKeyboardButton("🎶 Get Spotify Code", callback_data=CB_GET_CODE)],
        [InlineKeyboardButton("🎁 Redeem Spotify Code", callback_data=CB_REDEEM)],
        [InlineKeyboardButton("👤 Account Status", callback_data=CB_STATUS)],
        [InlineKeyboardButton("🔐 Session Management", callback_data=CB_SESSION_MGR)],
        [InlineKeyboardButton("❌ Logout / Clear Session", callback_data=CB_LOGOUT)],
    ])


def get_region_keyboard() -> InlineKeyboardMarkup:
    """Build region selection keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇳 India (en_in)", callback_data=CB_REGION_IN),
            InlineKeyboardButton("🇬🇧 UK (en_gb)", callback_data=CB_REGION_GB),
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data=CB_MAIN_MENU)],
    ])


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=CB_CONFIRM),
            InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL),
        ],
    ])


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Back to menu button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data=CB_MAIN_MENU)],
    ])


# ── Helper Functions ──────────────────────────────────────

async def send_progress(query_or_msg, text: str):
    """Send a progress update message."""
    try:
        if hasattr(query_or_msg, "message") and query_or_msg.message:
            # It's a CallbackQuery
            await query_or_msg.message.reply_text(text)
        elif hasattr(query_or_msg, "reply_text"):
            # It's a Message
            await query_or_msg.reply_text(text)
    except Exception as e:
        logger.error(f"Failed to send progress: {e}")


async def send_error(update: Update, error_type: str, next_steps: str):
    """Send a formatted error message with next steps."""
    text = (
        f"❌ **Error:** {error_type}\n\n"
        f"📋 **Next steps:**\n{next_steps}"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_back_keyboard()
        )
    elif update.message:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_back_keyboard()
        )


async def delete_sensitive_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Delete a message containing sensitive data (like passwords)."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Could not delete sensitive message: {e}")


def get_bot_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Retrieve shared bot resources from context.bot_data."""
    return {
        "db": context.bot_data.get("db"),
        "cred": context.bot_data.get("cred"),
        "hm": context.bot_data.get("hm_client"),
        "spotify": context.bot_data.get("spotify_client"),
        "browser": context.bot_data.get("browser"),
    }
