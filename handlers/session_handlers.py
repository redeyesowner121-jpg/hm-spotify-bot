"""
Session handlers — account status, session management, and logout.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from security import authorized_only, mask_email
from handlers.common import (
    CB_STATUS,
    CB_SESSION_MGR,
    CB_LOGOUT,
    CB_CONFIRM,
    CB_CANCEL,
    get_confirm_keyboard,
    get_back_keyboard,
    get_bot_data,
)

logger = logging.getLogger(__name__)

# Callback data for logout confirmation
CB_LOGOUT_CONFIRM = "logout_confirm"
CB_LOGOUT_CANCEL = "logout_cancel"


# ── Account Status ────────────────────────────────────────

@authorized_only
async def account_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stored account info and session status."""
    query = update.callback_query
    await query.answer()

    resources = get_bot_data(context)
    db = resources["db"]
    cred = resources["cred"]

    accounts = await db.get_all_accounts()
    sessions = await db.get_active_sessions()
    operations = await db.get_operations(5)

    text = "👤 *Account Status*\n\n"

    # Accounts
    if accounts:
        text += "📋 *Registered Accounts:*\n"
        for acc in accounts:
            try:
                email = mask_email(cred.decrypt(acc["email_encrypted"]))
            except Exception:
                email = "***"
            service = acc["service"].upper()
            status = acc["status"]
            region = acc.get("region", "—")
            text += f"  • {service}: {email} ({status})"
            if region and region != "—":
                text += f" [{region}]"
            text += "\n"
    else:
        text += "📋 No accounts registered yet.\n"

    text += "\n"

    # Sessions
    if sessions:
        text += "🔐 *Active Sessions:*\n"
        for s in sessions:
            text += f"  • {s['service'].upper()} — updated {s['updated_at']}\n"
    else:
        text += "🔐 No active sessions.\n"

    text += "\n"

    # Recent operations
    if operations:
        text += "📝 *Recent Operations:*\n"
        for op in operations:
            text += f"  • [{op['status']}] {op['op_type']} — {op['created_at']}\n"

    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )


# ── Session Management ────────────────────────────────────

@authorized_only
async def session_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show session details and management options."""
    query = update.callback_query
    await query.answer()

    resources = get_bot_data(context)
    db = resources["db"]

    sessions = await db.get_active_sessions()

    text = "🔐 *Session Management*\n\n"

    if sessions:
        for s in sessions:
            text += (
                f"  🔸 *{s['service'].upper()}*\n"
                f"     Created: {s['created_at']}\n"
                f"     Updated: {s['updated_at']}\n\n"
            )
        text += "Use *Logout / Clear Session* to remove all sessions."
    else:
        text += "No active sessions.\n\nCreate an account or login to establish a session."

    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )


# ── Logout / Clear Session ───────────────────────────────

@authorized_only
async def logout_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for confirmation before clearing all sessions and data."""
    query = update.callback_query
    await query.answer()

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, clear everything", callback_data=CB_LOGOUT_CONFIRM),
            InlineKeyboardButton("❌ Cancel", callback_data=CB_LOGOUT_CANCEL),
        ],
    ])

    await query.edit_message_text(
        "❌ *Logout / Clear Session*\n\n"
        "⚠️ This will:\n"
        "  • Delete all stored sessions (H&M + Spotify)\n"
        "  • Clear encrypted credentials from database\n"
        "  • Remove all operation logs\n\n"
        "Are you sure?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@authorized_only
async def logout_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all sessions and data."""
    query = update.callback_query
    await query.answer()

    resources = get_bot_data(context)
    db = resources["db"]
    browser = resources["browser"]

    # Clear database
    await db.clear_all_data()

    # Clear browser sessions
    await browser.clear_session("hm")
    await browser.clear_session("spotify")

    # Clear user_data
    context.user_data.clear()

    await query.edit_message_text(
        "✅ *All sessions and data cleared.*\n\n"
        "🔒 All stored credentials, sessions, and logs have been removed.",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    logger.info("User performed full logout — all data cleared")


@authorized_only
async def logout_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User cancelled logout."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ Logout cancelled. Your sessions are intact.",
        reply_markup=get_back_keyboard(),
    )


# ── Handler Registration ─────────────────────────────────

def get_session_handlers() -> list:
    """Return all session-related handlers."""
    return [
        CallbackQueryHandler(account_status, pattern=f"^{CB_STATUS}$"),
        CallbackQueryHandler(session_management, pattern=f"^{CB_SESSION_MGR}$"),
        CallbackQueryHandler(logout_prompt, pattern=f"^{CB_LOGOUT}$"),
        CallbackQueryHandler(logout_confirmed, pattern=f"^{CB_LOGOUT_CONFIRM}$"),
        CallbackQueryHandler(logout_cancelled, pattern=f"^{CB_LOGOUT_CANCEL}$"),
    ]
