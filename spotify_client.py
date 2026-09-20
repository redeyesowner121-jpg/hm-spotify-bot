"""
Spotify Client — browser automation for account creation, login, and code redemption.

Uses only official Spotify website interfaces. Pauses on CAPTCHA — never bypasses.
Selectors may need calibration if Spotify updates their HTML.
"""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]

SPOTIFY_URLS = {
    "signup": "https://www.spotify.com/signup",
    "login": "https://accounts.spotify.com/login",
    "redeem": "https://www.spotify.com/redeem/",
}


class SpotifyClient:
    """Automates Spotify official website for personal account management."""

    def __init__(self, browser_mgr, db, cred_mgr):
        self.browser = browser_mgr
        self.db = db
        self.cred = cred_mgr

    # ── Account Creation ──────────────────────────────────────

    async def create_account(
        self,
        email: str,
        password: str,
        display_name: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """
        Create a Spotify account via the official signup page.
        display_name is derived from the email prefix (text before @).
        """
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening Spotify signup page...")
            context = await self.browser.get_context("spotify")
            page = await context.new_page()

            await page.goto(SPOTIFY_URLS["signup"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            await progress_cb("📝 Filling Spotify registration form...")

            # Spotify signup is typically a multi-step form
            # Step 1: Email
            email_selectors = [
                "input[name='email']",
                "input[type='email']",
                "#email",
                "input[data-testid='email-input']",
                "input[placeholder*='email' i]",
            ]
            for sel in email_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(email)
                        break
                except Exception:
                    continue

            # Click next/continue if multi-step
            next_selectors = [
                "button[data-testid='submit']",
                "button:has-text('Next')",
                "button:has-text('Continue')",
                "button[type='submit']",
            ]
            for sel in next_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # Step 2: Password
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "#password",
                "input[data-testid='password-input']",
            ]
            for sel in password_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(password)
                        break
                except Exception:
                    continue

            # Click next again if multi-step
            for sel in next_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            # Step 3: Display name
            name_selectors = [
                "input[name='displayname']",
                "input[name='display_name']",
                "input[name='name']",
                "input[data-testid='displayname-input']",
                "#displayname",
                "input[placeholder*='name' i]",
            ]
            for sel in name_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(display_name)
                        break
                except Exception:
                    continue

            # Step 4: Date of birth (fill with a generic adult date if fields exist)
            dob_fields = {
                "input[name='day']": "15",
                "#day": "15",
                "input[name='month']": "06",
                "#month": "06",
                "input[name='year']": "1995",
                "#year": "1995",
            }
            for sel, val in dob_fields.items():
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(val)
                except Exception:
                    continue

            # Handle month dropdown if it's a select
            month_select_selectors = [
                "select[name='month']",
                "select#month",
            ]
            for sel in month_select_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.select_option(value="06")
                        break
                except Exception:
                    continue

            # Step 5: Gender (select if required)
            gender_selectors = [
                "input[name='gender'][value='neutral']",
                "input[name='gender'][value='prefer-not-to-say']",
                "input[name='gender'][value='non-binary']",
            ]
            for sel in gender_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    continue

            # Handle terms checkbox
            terms_selectors = [
                "input[name*='terms']",
                "input[name*='consent']",
                "[data-testid*='terms'] input",
                "input[type='checkbox']",
            ]
            for sel in terms_selectors:
                try:
                    checkboxes = await page.query_selector_all(sel)
                    for cb in checkboxes:
                        if await cb.is_visible() and not await cb.is_checked():
                            await cb.check()
                            await asyncio.sleep(0.3)
                except Exception:
                    continue

            await progress_cb("✅ Form filled. Submitting registration...")

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA appeared! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # Final submit
            submit_selectors = [
                "button[data-testid='submit']",
                "button[type='submit']",
                "button:has-text('Sign up')",
                "button:has-text('Create account')",
                "button:has-text('Register')",
                "button:has-text('Join')",
            ]
            for sel in submit_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        break
                except Exception:
                    continue

            await asyncio.sleep(4)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA after submission! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # Analyze result
            page_content = await page.content()
            current_url = page.url.lower()

            if any(x in page_content.lower() for x in [
                "already registered", "already exists", "already have an account",
                "email is taken", "already been used",
            ]):
                return {
                    "success": False,
                    "message": "❌ Email already registered with Spotify",
                    "details": "Try logging in instead.",
                }

            if any(x in page_content.lower() for x in [
                "verify your email", "confirmation", "check your inbox",
            ]):
                await self.browser.save_session("spotify", context)
                email_enc = self.cred.encrypt(email)
                pass_enc = self.cred.encrypt(password)
                await self.db.save_account(email_enc, pass_enc, "spotify", "pending_verification", display_name=display_name)
                await self.db.log_operation("spotify_create", "pending_verification", email)
                return {
                    "success": True,
                    "message": "📧 Spotify account created — email verification may be required",
                    "details": "Check your inbox if needed.",
                    "email": email,
                }

            if any(x in current_url for x in ["download", "welcome", "account", "home"]):
                await self.browser.save_session("spotify", context)
                email_enc = self.cred.encrypt(email)
                pass_enc = self.cred.encrypt(password)
                await self.db.save_account(email_enc, pass_enc, "spotify", "active", display_name=display_name)
                await self.db.log_operation("spotify_create", "success", email)
                return {
                    "success": True,
                    "message": "✅ Spotify account created successfully!",
                    "email": email,
                    "display_name": display_name,
                }

            # Ambiguous
            await self.browser.save_session("spotify", context)
            email_enc = self.cred.encrypt(email)
            pass_enc = self.cred.encrypt(password)
            await self.db.save_account(email_enc, pass_enc, "spotify", "unknown", display_name=display_name)
            await self.db.log_operation("spotify_create", "unknown", email)
            return {
                "success": True,
                "message": "⚠️ Registration submitted — please verify manually",
                "email": email,
            }

        except Exception as e:
            logger.error(f"Spotify registration error: {e}", exc_info=True)
            await self.db.log_operation("spotify_create", "error", str(e))
            return {"success": False, "message": f"❌ Registration failed: {e}"}
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    # ── Login ─────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """Log into Spotify with email/password. Saves session on success."""
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening Spotify login page...")
            context = await self.browser.get_context("spotify")
            page = await context.new_page()

            await page.goto(SPOTIFY_URLS["login"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Dismiss cookie banner if present
            try:
                cookie_btn = await page.query_selector("button#onetrust-accept-btn-handler, button:has-text('Accept Cookies')")
                if cookie_btn and await cookie_btn.is_visible():
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            await progress_cb("🔑 Entering Spotify credentials...")

            # Fill email/username
            for sel in ["input[id='login-username']", "input[name='username']", "input[type='email']", "input[type='text']"]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(email)
                        break
                except Exception:
                    continue

            # Fill password
            for sel in ["input[id='login-password']", "input[name='password']", "input[type='password']"]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(password)
                        break
                except Exception:
                    continue

            # Submit
            submitted = False
            for sel in ["button[data-testid='login-button']", "button[id='login-button']", "button[type='submit']", "button:has-text('Log in')", "button:has-text('Sign in')"]:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                try:
                    await page.keyboard.press("Enter")
                    submitted = True
                except Exception:
                    pass

            # Wait for navigation away from /login
            try:
                await page.wait_for_url(lambda u: "/login" not in u.lower(), timeout=12000)
            except Exception:
                pass

            await asyncio.sleep(3)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA appeared! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            current_url = page.url.lower()
            page_content = await page.content()

            # Check for 2FA/suspicious login
            if any(x in page_content.lower() for x in ["two-factor", "2fa", "verification code", "suspicious", "confirm your identity"]):
                await progress_cb(
                    "🔐 2FA or suspicious login challenge detected!\n"
                    "Please complete the verification manually.\n"
                    "Waiting up to 5 minutes..."
                )
                try:
                    await page.wait_for_url("**/account/**", timeout=300000)
                except Exception:
                    return {"success": False, "message": "2FA/verification timed out"}

            # Check for incorrect credentials
            if any(x in page_content.lower() for x in ["incorrect", "wrong password", "invalid username", "doesn't match"]):
                return {
                    "success": False,
                    "message": "❌ Spotify login failed — incorrect credentials",
                    "details": "Check your email and password.",
                }

            # Check if login authenticated successfully (via auth cookies or navigation away from login)
            cookies = await context.cookies()
            auth_cookie_names = {"sp_dc", "sp_t", "sp_key", "sp_m"}
            has_auth_cookie = any(c.get("name") in auth_cookie_names for c in cookies)

            if ("/login" not in current_url) or has_auth_cookie or any(x in current_url for x in ["account", "player", "home", "open.spotify"]):
                await self.browser.save_session("spotify", context)
                email_enc = self.cred.encrypt(email)
                pass_enc = self.cred.encrypt(password)
                await self.db.save_account(email_enc, pass_enc, "spotify", "active")
                await self.db.log_operation("spotify_login", "success", email)
                return {
                    "success": True,
                    "message": "✅ Logged into Spotify successfully!",
                    "email": email,
                }

            # Still stuck on login page
            return {
                "success": False,
                "message": "❌ Spotify login failed — still on login page",
                "details": "Please check your email and password, or check if Spotify prompted a verification challenge.",
            }

        except Exception as e:
            logger.error(f"Spotify login error: {e}", exc_info=True)
            return {"success": False, "message": f"❌ Login failed: {e}"}
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    # ── Redeem Code ───────────────────────────────────────────

    async def redeem_code(
        self,
        code: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """
        Redeem a voucher/promo code or full promo URL on Spotify.
        Requires an active Spotify session.
        """
        context = None
        page = None

        try:
            target_url = code if code.startswith("http") else SPOTIFY_URLS["redeem"]
            await progress_cb(f"🌐 Opening Spotify redeem page...")
            context = await self.browser.get_context("spotify")
            page = await context.new_page()

            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check if redirected to login
            if "login" in page.url.lower() or "signin" in page.url.lower():
                return {
                    "success": False,
                    "message": "🔑 Spotify session expired — login required",
                    "need_login": True,
                }

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # If the target was a promo URL, a button like 'Confirm' or 'Claim' might be directly clickable
            promo_action_selectors = [
                "button:has-text('Redeem')",
                "button:has-text('Claim')",
                "button:has-text('Get offer')",
                "button:has-text('Continue')",
                "button:has-text('Confirm')",
                "button[data-testid*='redeem']",
            ]

            code_entered = False
            # If it's a raw voucher code, fill input
            if not code.startswith("http"):
                await progress_cb("🎁 Entering redeem code...")
                code_selectors = [
                    "input[name='code']",
                    "input[name='pin']",
                    "input[type='text']",
                    "input[placeholder*='code' i]",
                    "input[placeholder*='pin' i]",
                    "input[data-testid*='code']",
                    "#code",
                ]
                for sel in code_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el and await el.is_visible():
                            await el.fill(code)
                            code_entered = True
                            break
                    except Exception:
                        continue

            if not code_entered:
                return {
                    "success": False,
                    "message": "❌ Could not find code input field on redeem page",
                    "details": "Spotify may have changed their page layout. Try redeeming manually.",
                }

            # Submit the code
            submit_selectors = [
                "button[type='submit']",
                "button:has-text('Redeem')",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "button[data-testid*='redeem']",
            ]
            for sel in submit_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        break
                except Exception:
                    continue

            await asyncio.sleep(4)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA appeared! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # Analyze result
            page_content = await page.content()
            current_url = page.url

            if any(x in page_content.lower() for x in [
                "successfully redeemed", "congratulations", "your subscription",
                "premium activated", "code applied", "redeemed successfully",
            ]):
                await self.browser.save_session("spotify", context)
                await self.db.log_operation("spotify_redeem", "success", f"Code redeemed")
                return {
                    "success": True,
                    "message": "🎉 Spotify code redeemed successfully!",
                    "result_url": current_url,
                }

            if any(x in page_content.lower() for x in [
                "invalid", "expired", "already been used", "not valid",
                "incorrect code", "wrong code",
            ]):
                await self.db.log_operation("spotify_redeem", "failed", "Invalid or expired code")
                return {
                    "success": False,
                    "message": "❌ Redemption failed — invalid or expired code",
                    "details": "The code may have already been used or is not valid.",
                }

            if any(x in page_content.lower() for x in [
                "already have premium", "existing subscription",
            ]):
                return {
                    "success": False,
                    "message": "ℹ️ You already have an active Spotify Premium subscription",
                    "details": "The code cannot be applied to an account with an existing subscription.",
                }

            # Ambiguous result
            await self.browser.save_session("spotify", context)
            await self.db.log_operation("spotify_redeem", "unknown", "Result unclear")
            return {
                "success": True,
                "message": "⚠️ Code submitted — please verify redemption manually",
                "result_url": current_url,
            }

        except Exception as e:
            logger.error(f"Spotify redeem error: {e}", exc_info=True)
            await self.db.log_operation("spotify_redeem", "error", str(e))
            return {"success": False, "message": f"❌ Redemption failed: {e}"}
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
