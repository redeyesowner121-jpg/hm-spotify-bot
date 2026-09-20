"""
Spotify handlers — account creation, code retrieval, and code redemption flows.

Flows:
  1. Create Spotify Account: Email → Password → Confirm → Automation
  2. Get Spotify Code: Check H&M session → Region → (Login if needed) → Retrieve
  3. Redeem Spotify Code: Check code → (Spotify login if needed) → Confirm → Redeem
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from security import authorized_only, mask_email, mask_password, extract_name_from_email
from handlers.common import (
    CB_SPOTIFY_CREATE,
    CB_GET_CODE,
    CB_REDEEM,
    CB_REGION_IN,
    CB_REGION_GB,
    CB_CONFIRM,
    CB_CANCEL,
    CB_MAIN_MENU,
    get_region_keyboard,
    get_confirm_keyboard,
    get_back_keyboard,
    delete_sensitive_message,
    get_bot_data,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 1. CREATE SPOTIFY ACCOUNT
# ═══════════════════════════════════════════════════════════

SP_CREATE_EMAIL = 100
SP_CREATE_PASSWORD = 101
SP_CREATE_CONFIRM = 102


@authorized_only
async def spotify_create_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: user clicked 'Create Spotify Account'."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎵 *Create Spotify Account*\n\n"
        "📧 Please send your *email address*:\n\n"
        "_The display name will be automatically extracted from your email prefix._",
        parse_mode="Markdown",
    )
    return SP_CREATE_EMAIL


@authorized_only
async def spotify_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Email received for Spotify signup."""
    email = update.message.text.strip()
    if "@" not in email or "." not in email:
        await update.message.reply_text("⚠️ Invalid email. Please try again:")
        return SP_CREATE_EMAIL

    context.user_data["sp_email"] = email
    context.user_data["sp_display_name"] = extract_name_from_email(email)

    await update.message.reply_text(
        "🔑 Now send your *password* for the new Spotify account:",
        parse_mode="Markdown",
    )
    return SP_CREATE_PASSWORD


@authorized_only
async def spotify_password_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Password received for Spotify signup."""
    password = update.message.text.strip()

    if len(password) < 8:
        await update.message.reply_text(
            "⚠️ Password too short (minimum 8 characters). Try again:",
            parse_mode="Markdown",
        )
        return SP_CREATE_PASSWORD

    context.user_data["sp_password"] = password
    email = context.user_data.get("sp_email", "")
    display_name = context.user_data.get("sp_display_name", "")

    await update.message.reply_text(
        f"🎵 *Confirm Spotify Account Creation*\n\n"
        f"📧 Email: `{mask_email(email)}`\n"
        f"🔑 Password: `{mask_password(password)}`\n"
        f"👤 Display Name: `{display_name}`\n\n"
        f"Proceed with registration?",
        parse_mode="Markdown",
        reply_markup=get_confirm_keyboard(),
    )
    return SP_CREATE_CONFIRM


@authorized_only
async def spotify_create_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User confirmed Spotify account creation."""
    query = update.callback_query
    await query.answer()

    email = context.user_data.get("sp_email", "")
    password = context.user_data.get("sp_password", "")
    display_name = context.user_data.get("sp_display_name", "")

    await query.edit_message_text(
        "⏳ *Creating Spotify account...*\n\nPlease wait.",
        parse_mode="Markdown",
    )

    resources = get_bot_data(context)
    spotify = resources["spotify"]
    chat_id = query.message.chat_id

    async def progress_cb(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    result = await spotify.create_account(email, password, display_name, progress_cb)

    # Keep credentials in memory and DB until Clear Session is clicked

    if result.get("success"):
        text = (
            f"🎵 *Spotify Account Creation Result*\n\n"
            f"📧 Email: `{mask_email(email)}`\n"
            f"👤 Name: `{display_name}`\n"
            f"📊 Status: {result['message']}\n"
        )
    else:
        text = f"🎵 *Spotify Account Creation Failed*\n\n❌ {result['message']}\n"

    if result.get("details"):
        text += f"\n📋 {result['details']}"

    await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
# 2. GET SPOTIFY CODE (from H&M profile)
# ═══════════════════════════════════════════════════════════

GC_SELECT_REGION = 200
GC_ENTER_EMAIL = 201
GC_ENTER_PASSWORD = 202
GC_PROCESSING = 203


@authorized_only
async def get_code_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: user clicked 'Get Spotify Code'."""
    query = update.callback_query
    await query.answer()

    resources = get_bot_data(context)
    db = resources["db"]
    cred = resources["cred"]

    # Check if there's an active H&M session or saved account
    session = await db.get_session("hm")
    if not context.user_data.get("gc_email"):
        saved_acc = await db.get_account("hm")
        if saved_acc:
            try:
                context.user_data["gc_email"] = cred.decrypt(saved_acc["email_encrypted"])
                context.user_data["gc_password"] = cred.decrypt(saved_acc["password_encrypted"])
            except Exception:
                pass

    acc_info = ""
    if context.user_data.get("gc_email"):
        acc_info = f"\n👤 Account: `{mask_email(context.user_data['gc_email'])}`"

    if session or context.user_data.get("gc_email"):
        await query.edit_message_text(
            f"🎶 *Get Spotify Code from H&M*{acc_info}\n\n"
            f"Select your H&M region:",
            parse_mode="Markdown",
            reply_markup=get_region_keyboard(),
        )
        context.user_data["gc_has_session"] = bool(session)
    else:
        await query.edit_message_text(
            "🎶 *Get Spotify Code from H&M*\n\n"
            "⚠️ No active H&M session. You need to login first.\n\n"
            "Select your H&M region:",
            parse_mode="Markdown",
            reply_markup=get_region_keyboard(),
        )
        context.user_data["gc_has_session"] = False

    return GC_SELECT_REGION


@authorized_only
async def gc_region_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Region selected for code retrieval."""
    query = update.callback_query
    await query.answer()

    context.user_data["gc_region"] = "en_in" if query.data == CB_REGION_IN else "en_gb"

    if context.user_data.get("gc_has_session"):
        return await gc_process(update, context)
    elif context.user_data.get("gc_email") and context.user_data.get("gc_password"):
        return await gc_auto_login_and_retrieve(update, context)
    else:
        await query.edit_message_text(
            "🔑 Please send your *H&M email address* to login:",
            parse_mode="Markdown",
        )
        return GC_ENTER_EMAIL


@authorized_only
async def gc_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("⚠️ Invalid email. Try again:")
        return GC_ENTER_EMAIL
    context.user_data["gc_email"] = email
    await update.message.reply_text(
        "🔑 Send your *H&M password*:",
        parse_mode="Markdown",
    )
    return GC_ENTER_PASSWORD


@authorized_only
async def gc_password_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    context.user_data["gc_password"] = password

    return await gc_auto_login_and_retrieve(update, context)


async def gc_auto_login_and_retrieve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log into H&M and retrieve code, keeping credentials saved."""
    query = update.callback_query
    chat_id = query.message.chat_id if query else update.message.chat_id
    region = context.user_data.get("gc_region", "en_in")
    email = context.user_data.get("gc_email", "")
    password = context.user_data.get("gc_password", "")

    resources = get_bot_data(context)
    hm_client = resources["hm"]

    async def progress_cb(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    await context.bot.send_message(chat_id=chat_id, text="⏳ Logging into H&M with saved credentials...")

    login_result = await hm_client.login(email, password, region, progress_cb)

    if not login_result.get("success"):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ H&M login failed: {login_result.get('message', 'Unknown error')}",
            reply_markup=get_back_keyboard(),
        )
        return ConversationHandler.END

    # Now get the code
    await context.bot.send_message(chat_id=chat_id, text="✅ Login successful! Retrieving Spotify code...")

    result = await hm_client.get_spotify_code(region, progress_cb)

    if result.get("success"):
        redeem_url = result.get("redeem_url")
        code = result.get("code")
        text = "🎉 *Spotify Offer Retrieved!*\n\n"
        if redeem_url:
            text += f"🔗 *Redeem Link:*\n{redeem_url}\n\n"
        if code and code != redeem_url:
            text += f"🎟️ *Voucher Code:* `{code}`\n\n"
        text += "👉 Click the redeem link to activate your Spotify Premium offer!"
    else:
        text = f"🎶 *Spotify Code Retrieval*\n\n{result.get('message', 'Failed')}"
        if result.get("details"):
            text += f"\n\n📋 {result['details']}"

    await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


async def gc_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retrieve Spotify code with existing session."""
    query = update.callback_query
    region = context.user_data.get("gc_region", "en_in")
    chat_id = query.message.chat_id

    await query.edit_message_text("⏳ *Retrieving Spotify code from H&M profile...*", parse_mode="Markdown")

    resources = get_bot_data(context)
    hm_client = resources["hm"]

    async def progress_cb(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    result = await hm_client.get_spotify_code(region, progress_cb)

    if result.get("need_login"):
        if context.user_data.get("gc_email") and context.user_data.get("gc_password"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔑 Session refreshed — logging in automatically with your saved credentials...",
            )
            return await gc_auto_login_and_retrieve(update, context)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔑 H&M session expired. Please send your *H&M email* to login:",
                parse_mode="Markdown",
            )
            context.user_data["gc_has_session"] = False
            return GC_ENTER_EMAIL

    if result.get("success"):
        redeem_url = result.get("redeem_url")
        code = result.get("code")
        text = "🎉 *Spotify Offer Retrieved!*\n\n"
        if redeem_url:
            text += f"🔗 *Redeem Link:*\n{redeem_url}\n\n"
        if code and code != redeem_url:
            text += f"🎟️ *Voucher Code:* `{code}`\n\n"
        text += "👉 Click the redeem link to activate your Spotify Premium offer!"
    else:
        text = f"🎶 *Spotify Code Retrieval*\n\n{result.get('message', 'Failed')}"
        if result.get("details"):
            text += f"\n\n📋 {result['details']}"

    await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
# 3. REDEEM SPOTIFY CODE
# ═══════════════════════════════════════════════════════════

RD_ENTER_CODE = 300
RD_ENTER_EMAIL = 301
RD_ENTER_PASSWORD = 302
RD_CONFIRM = 303


@authorized_only
async def redeem_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: user clicked 'Redeem Spotify Code'."""
    query = update.callback_query
    await query.answer()

    resources = get_bot_data(context)
    db = resources["db"]
    cred = resources["cred"]

    # Check for previously retrieved code
    code_record = await db.get_latest_spotify_code()
    if code_record:
        code = cred.decrypt(code_record["code_encrypted"])
        # Invalidate any junk code scraped accidentally (pure English words, no digits = not a real code)
        JUNK_CODES = {
            "permission", "undefined", "cookie", "accept", "submit", "button", "none", "trial",
            "subscribe", "standard", "membership", "overview", "benefit", "voucher", "account",
            "settings", "profile", "details", "password", "continue", "register", "redeem",
            "cancel", "login", "signup", "logout", "privacy", "terms", "help", "support",
            "home", "index", "about", "contact", "error", "page", "month", "months",
        }
        # Also reject pure-letter strings with no digits (real codes always contain digits)
        is_junk = (
            code.lower().strip() in JUNK_CODES
            or (code.isalpha() and not any(ch.isdigit() for ch in code))
        )
        if is_junk:
            await db.update_spotify_code_status(code_record["id"], "invalid")
            code_record = None

    if code_record:
        context.user_data["rd_code"] = code
        context.user_data["rd_code_id"] = code_record["id"]

        # Check Spotify session and saved account
        sp_session = await db.get_session("spotify")
        if not context.user_data.get("rd_email"):
            saved_acc = await db.get_account("spotify")
            if saved_acc:
                try:
                    context.user_data["rd_email"] = cred.decrypt(saved_acc["email_encrypted"])
                    context.user_data["rd_password"] = cred.decrypt(saved_acc["password_encrypted"])
                except Exception:
                    pass

        if sp_session or (context.user_data.get("rd_email") and context.user_data.get("rd_password")):
            # Directly process redemption without asking confirmation
            return await rd_process(update, context)
        else:
            await query.edit_message_text(
                f"🎁 *Redeem Spotify Code*\n\n"
                f"🎟️ Code: `{code}`\n"
                f"⚠️ No active Spotify session — login required.\n\n"
                f"📧 Please send your *Spotify email*:",
                parse_mode="Markdown",
            )
            return RD_ENTER_EMAIL
    else:
        # No code available — ask user to enter one
        await query.edit_message_text(
            "🎁 *Redeem Spotify Code*\n\n"
            "ℹ️ No previously retrieved code found.\n\n"
            "📝 Please enter the code to redeem, or use *Get Spotify Code* first:",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard(),
        )
        return RD_ENTER_CODE


@authorized_only
async def rd_code_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User manually entered a code."""
    code = update.message.text.strip()
    if len(code) < 5:
        await update.message.reply_text("⚠️ Code seems too short. Please try again:")
        return RD_ENTER_CODE

    context.user_data["rd_code"] = code

    resources = get_bot_data(context)
    db = resources["db"]
    cred = resources["cred"]
    sp_session = await db.get_session("spotify")

    if not context.user_data.get("rd_email"):
        saved_acc = await db.get_account("spotify")
        if saved_acc:
            try:
                context.user_data["rd_email"] = cred.decrypt(saved_acc["email_encrypted"])
                context.user_data["rd_password"] = cred.decrypt(saved_acc["password_encrypted"])
            except Exception:
                pass

    if sp_session or (context.user_data.get("rd_email") and context.user_data.get("rd_password")):
        await update.message.reply_text(
            f"🎁 *Redeem Spotify Code*\n\n"
            f"🎟️ Code: `{code}`\n\n"
            f"Redeem this code now?",
            parse_mode="Markdown",
            reply_markup=get_confirm_keyboard(),
        )
        return RD_CONFIRM
    else:
        await update.message.reply_text(
            "⚠️ No active Spotify session. Please send your *Spotify email*:",
            parse_mode="Markdown",
        )
        return RD_ENTER_EMAIL


@authorized_only
async def rd_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text("⚠️ Invalid email. Try again:")
        return RD_ENTER_EMAIL
    context.user_data["rd_email"] = email
    await update.message.reply_text(
        "🔑 Send your *Spotify password*:",
        parse_mode="Markdown",
    )
    return RD_ENTER_PASSWORD


@authorized_only
async def rd_password_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    context.user_data["rd_password"] = password

    # Login to Spotify
    resources = get_bot_data(context)
    spotify = resources["spotify"]
    chat_id = update.message.chat_id
    email = context.user_data.get("rd_email", "")

    async def progress_cb(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    await context.bot.send_message(chat_id=chat_id, text="⏳ Logging into Spotify...")
    login_result = await spotify.login(email, password, progress_cb)

    if not login_result.get("success"):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Spotify login failed: {login_result.get('message')}",
            reply_markup=get_back_keyboard(),
        )
        return ConversationHandler.END

    code = context.user_data.get("rd_code", "")
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ Spotify login successful!\n\n"
            f"🎁 *Redeem this code now?*\n"
            f"🎟️ Code: `{code}`"
        ),
        parse_mode="Markdown",
        reply_markup=get_confirm_keyboard(),
    )
    return RD_CONFIRM


@authorized_only
async def rd_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User confirmed redemption. Run browser automation."""
    query = update.callback_query
    await query.answer()

    code = context.user_data.get("rd_code", "")
    chat_id = query.message.chat_id

    resources = get_bot_data(context)
    spotify = resources["spotify"]
    db = resources["db"]

    async def progress_cb(msg):
        await context.bot.send_message(chat_id=chat_id, text=msg)

    # Check if we need to auto-login to Spotify first
    sp_session = await db.get_session("spotify")
    if not sp_session and context.user_data.get("rd_email") and context.user_data.get("rd_password"):
        await query.edit_message_text("⏳ *Logging into Spotify with saved account...*", parse_mode="Markdown")
        login_res = await spotify.login(context.user_data["rd_email"], context.user_data["rd_password"], progress_cb)
        if not login_res.get("success"):
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Spotify login failed: {login_res.get('message')}")
            return ConversationHandler.END

    await query.edit_message_text(
        f"⏳ *Redeeming Spotify code...*\n\n🎟️ `{code}`",
        parse_mode="Markdown",
    )

    result = await spotify.redeem_code(code, progress_cb)

    # Update code status if we had a DB record
    code_id = context.user_data.get("rd_code_id")
    if code_id:
        status = "redeemed" if result.get("success") else "failed"
        await db.update_spotify_code_status(code_id, status)

    if result.get("need_login"):
        if context.user_data.get("rd_email") and context.user_data.get("rd_password"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔑 Spotify session refreshed — logging in automatically with your saved credentials...",
            )
            login_res = await spotify.login(context.user_data["rd_email"], context.user_data["rd_password"], progress_cb)
            if login_res.get("success"):
                result = await spotify.redeem_code(code, progress_cb)

        if result.get("need_login"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔑 Spotify session expired. Please send your *Spotify email*:",
                parse_mode="Markdown",
            )
            return RD_ENTER_EMAIL

    if result.get("success"):
        text = f"🎁 *Spotify Code Redeemed!*\n\n✅ {result['message']}"
        if result.get("result_url"):
            text += f"\n\n🔗 [View Result]({result['result_url']})"
    else:
        text = f"🎁 *Spotify Redemption*\n\n{result.get('message', 'Failed')}"
        if result.get("details"):
            text += f"\n\n📋 {result['details']}"

    await context.bot.send_message(
        chat_id=chat_id, text=text, parse_mode="Markdown",
        reply_markup=get_back_keyboard(), disable_web_page_preview=True,
    )
    return ConversationHandler.END


# ── Shared: Cancel & Fallback ─────────────────────────────

@authorized_only
async def spotify_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Only clear temporary operation code, preserve saved credentials and sessions
    context.user_data.pop("rd_code", None)
    context.user_data.pop("rd_code_id", None)
    await query.edit_message_text("❌ Operation cancelled.", reply_markup=get_back_keyboard())
    return ConversationHandler.END


async def spotify_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Unexpected input. Use buttons or /start to restart.",
        reply_markup=get_back_keyboard(),
    )
    return ConversationHandler.END


# ── Build ConversationHandlers ────────────────────────────

def get_spotify_create_handler() -> ConversationHandler:
    """Spotify account creation conversation."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(spotify_create_entry, pattern=f"^{CB_SPOTIFY_CREATE}$"),
        ],
        states={
            SP_CREATE_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, spotify_email_received),
            ],
            SP_CREATE_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, spotify_password_received),
            ],
            SP_CREATE_CONFIRM: [
                CallbackQueryHandler(spotify_create_confirmed, pattern=f"^{CB_CONFIRM}$"),
                CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_CANCEL}$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", spotify_fallback),
            CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_user=True,
        per_chat=True,
    )


def get_code_retrieval_handler() -> ConversationHandler:
    """Spotify code retrieval from H&M profile."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(get_code_entry, pattern=f"^{CB_GET_CODE}$"),
        ],
        states={
            GC_SELECT_REGION: [
                CallbackQueryHandler(gc_region_selected, pattern=f"^({CB_REGION_IN}|{CB_REGION_GB})$"),
                CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_MAIN_MENU}$"),
            ],
            GC_ENTER_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gc_email_received),
            ],
            GC_ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gc_password_received),
            ],
        },
        fallbacks=[
            CommandHandler("start", spotify_fallback),
            CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_user=True,
        per_chat=True,
    )


def get_redeem_handler() -> ConversationHandler:
    """Spotify code redemption conversation."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(redeem_entry, pattern=f"^{CB_REDEEM}$"),
        ],
        states={
            RD_ENTER_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rd_code_entered),
            ],
            RD_ENTER_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rd_email_received),
            ],
            RD_ENTER_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rd_password_received),
            ],
            RD_CONFIRM: [
                CallbackQueryHandler(rd_confirmed, pattern=f"^{CB_CONFIRM}$"),
                CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_CANCEL}$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", spotify_fallback),
            CallbackQueryHandler(spotify_cancelled, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_user=True,
        per_chat=True,
    )
