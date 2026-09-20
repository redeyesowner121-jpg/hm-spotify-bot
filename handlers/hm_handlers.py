"""
H&M handlers — account creation conversation flow via Telegram.

Flow: Button → Region Selection → Email → Password → Confirmation → Processing
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from security import authorized_only, mask_email, mask_password
from handlers.common import (
    CB_HM_CREATE,
    CB_REGION_IN,
    CB_REGION_GB,
    CB_CONFIRM,
    CB_CANCEL,
    CB_MAIN_MENU,
    get_region_keyboard,
    get_confirm_keyboard,
    get_back_keyboard,
    get_main_menu_keyboard,
    delete_sensitive_message,
    get_bot_data,
)

logger = logging.getLogger(__name__)

# Conversation states
HM_SELECT_REGION = 0
HM_ENTER_EMAIL = 1
HM_ENTER_PASSWORD = 2
HM_CONFIRM = 3


# ── Entry: Show region selection ─────────────────────────

@authorized_only
async def hm_create_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: user clicked 'Create H&M Account'."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🛒 *Create H&M Account*\n\nSelect your H&M region:",
        parse_mode="Markdown",
        reply_markup=get_region_keyboard(),
    )
    return HM_SELECT_REGION


# ── Step 1: Region selected → Ask for email ──────────────

@authorized_only
async def hm_region_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected a region. Ask for email."""
    query = update.callback_query
    await query.answer()

    if query.data == CB_REGION_IN:
        context.user_data["hm_region"] = "en_in"
        region_label = "🇮🇳 India"
    else:
        context.user_data["hm_region"] = "en_gb"
        region_label = "🇬🇧 United Kingdom"

    await query.edit_message_text(
        f"🛒 *Create H&M Account*\n\n"
        f"Region: {region_label}\n\n"
        f"📧 Please send your *email address*:",
        parse_mode="Markdown",
    )
    return HM_ENTER_EMAIL


# ── Step 2: Email received → Ask for password ────────────

@authorized_only
async def hm_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent email. Ask for password."""
    email = update.message.text.strip()

    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid email address. Please try again:"
        )
        return HM_ENTER_EMAIL

    context.user_data["hm_email"] = email

    await update.message.reply_text(
        "🔑 Now send your *password*:",
        parse_mode="Markdown",
    )
    return HM_ENTER_PASSWORD


# ── Step 3: Password received → Show confirmation ────────

@authorized_only
async def hm_password_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent password. Delete the message and show confirmation."""
    password = update.message.text.strip()

    # Immediately delete the password message from chat
    await delete_sensitive_message(
        context, update.message.chat_id, update.message.message_id
    )

    if len(password) < 6:
        await update.message.reply_text(
            "⚠️ Password is too short (minimum 6 characters). Please try again:",
            parse_mode="Markdown",
        )
        return HM_ENTER_PASSWORD

    context.user_data["hm_password"] = password

    region = context.user_data.get("hm_region", "en_in")
    email = context.user_data.get("hm_email", "")
    region_label = "🇮🇳 India" if region == "en_in" else "🇬🇧 United Kingdom"

    await update.message.reply_text(
        f"🛒 *Confirm H&M Account Creation*\n\n"
        f"📧 Email: `{mask_email(email)}`\n"
        f"🔑 Password: `{mask_password(password)}`\n"
        f"🌍 Region: {region_label}\n\n"
        f"Proceed with registration?",
        parse_mode="Markdown",
        reply_markup=get_confirm_keyboard(),
    )
    return HM_CONFIRM


# ── Step 4: Confirmed → Run browser automation ───────────

@authorized_only
async def hm_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User confirmed. Start browser automation."""
    query = update.callback_query
    await query.answer()

    email = context.user_data.get("hm_email", "")
    password = context.user_data.get("hm_password", "")
    region = context.user_data.get("hm_region", "en_in")

    await query.edit_message_text(
        "⏳ *Creating H&M account...*\n\nPlease wait, this may take a moment.",
        parse_mode="Markdown",
    )

    resources = get_bot_data(context)
    hm_client = resources["hm"]

    # Progress callback sends updates to the chat
    chat_id = query.message.chat_id

    async def progress_cb(msg: str):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    result = await hm_client.create_account(email, password, region, progress_cb)

    # Keep credentials in memory and DB until Clear Session is clicked

    # Build result message
    if result.get("success"):
        text = (
            f"🛒 *H&M Account Creation Result*\n\n"
            f"📧 Email: `{mask_email(email)}`\n"
            f"📊 Status: {result['message']}\n"
        )
        if result.get("details"):
            text += f"\n📋 {result['details']}"
    else:
        text = (
            f"🛒 *H&M Account Creation Failed*\n\n"
            f"❌ {result['message']}\n"
        )
        if result.get("details"):
            text += f"\n📋 {result['details']}"

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ── Cancelled ─────────────────────────────────────────────

@authorized_only
async def hm_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User cancelled the operation."""
    query = update.callback_query
    await query.answer()

    # Clear sensitive data
    context.user_data.pop("hm_password", None)
    context.user_data.pop("hm_email", None)

    await query.edit_message_text(
        "❌ H&M account creation cancelled.",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ── Fallback ──────────────────────────────────────────────

async def hm_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unexpected input during conversation."""
    await update.message.reply_text(
        "⚠️ Unexpected input. Use the buttons above or type /start to restart.",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ── Build ConversationHandler ─────────────────────────────

def get_hm_conversation_handler() -> ConversationHandler:
    """Build and return the H&M account creation conversation handler."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(hm_create_entry, pattern=f"^{CB_HM_CREATE}$"),
        ],
        states={
            HM_SELECT_REGION: [
                CallbackQueryHandler(hm_region_selected, pattern=f"^({CB_REGION_IN}|{CB_REGION_GB})$"),
                CallbackQueryHandler(hm_cancelled, pattern=f"^{CB_MAIN_MENU}$"),
            ],
            HM_ENTER_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, hm_email_received),
            ],
            HM_ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, hm_password_received),
            ],
            HM_CONFIRM: [
                CallbackQueryHandler(hm_confirmed, pattern=f"^{CB_CONFIRM}$"),
                CallbackQueryHandler(hm_cancelled, pattern=f"^{CB_CANCEL}$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", hm_fallback),
            MessageHandler(filters.ALL, hm_fallback),
        ],
        per_user=True,
        per_chat=True,
    )

