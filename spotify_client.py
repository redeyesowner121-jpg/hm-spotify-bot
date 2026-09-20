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

    async def login(
        self,
        email: str,
        password: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """Log into Spotify with email/password. Saves session ONLY on verified success."""
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening Spotify login page...")
            context = await self.browser.get_context("spotify")
            page = await context.new_page()

            await page.goto(SPOTIFY_URLS["login"], wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Dismiss cookie/consent banner
            for cookie_sel in [
                "button#onetrust-accept-btn-handler",
                "button[data-testid='accept-cookies-banner']",
                "button:has-text('Accept cookies')",
                "button:has-text('Accept')",
            ]:
                try:
                    btn = await page.query_selector(cookie_sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            await progress_cb("🔑 Entering Spotify credentials...")

            # Find username field — Spotify uses id="login-username"
            username_filled = False
            for sel in [
                "input[id='login-username']",
                "input[name='username']",
                "input[autocomplete='username']",
                "input[type='email']",
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.triple_click()
                        await el.fill(email)
                        username_filled = True
                        break
                except Exception:
                    continue

            if not username_filled:
                return {
                    "success": False,
                    "message": "❌ Could not find Spotify username field",
                    "details": "Spotify may have updated their login page. Try again.",
                }

            # Find password field — Spotify uses id="login-password"
            password_filled = False
            for sel in [
                "input[id='login-password']",
                "input[name='password']",
                "input[autocomplete='current-password']",
                "input[type='password']",
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.triple_click()
                        await el.fill(password)
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                return {
                    "success": False,
                    "message": "❌ Could not find Spotify password field",
                    "details": "Spotify may have updated their login page. Try again.",
                }

            # Small delay so browser registers the filled credentials
            await asyncio.sleep(0.5)

            # Click the Login/Submit button
            login_clicked = False
            for sel in [
                "button[data-testid='login-button']",
                "button[id='login-button']",
                "button[type='submit']",
                "button:has-text('Log in')",
                "button:has-text('Sign in')",
            ]:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        await btn.click()
                        login_clicked = True
                        break
                except Exception:
                    continue

            if not login_clicked:
                await page.keyboard.press("Enter")

            # ── Wait for the outcome — URL must change OR error must appear ──
            # Spotify either: redirects away from /login (success), or shows an error message (failure)
            try:
                # Wait up to 15s for either: URL change, error alert, or CAPTCHA
                await page.wait_for_function(
                    """() => {
                        const url = window.location.href.toLowerCase();
                        const gone = !url.includes('/login');
                        const err = document.querySelector(
                            '[data-testid="login-error"], #login__error-message, [class*="error"], [role="alert"]'
                        );
                        const hasErr = err && err.textContent.trim().length > 0;
                        return gone || hasErr;
                    }""",
                    timeout=15000,
                )
            except Exception:
                pass  # timed out — we'll check manually below

            await asyncio.sleep(2)

            current_url = page.url
            current_url_lower = current_url.lower()

            # 1. Check for error messages FIRST (wrong password, etc.)
            error_texts = []
            for err_sel in [
                "[data-testid='login-error']",
                "#login__error-message",
                "[class*='error-message']",
                "[class*='ErrorMessage']",
                "[role='alert']",
                "p[class*='error']",
                "span[class*='error']",
            ]:
                try:
                    err_el = await page.query_selector(err_sel)
                    if err_el and await err_el.is_visible():
                        txt = (await err_el.inner_text()).strip()
                        if txt:
                            error_texts.append(txt)
                except Exception:
                    continue

            page_text = await page.inner_text("body")
            error_keywords = [
                "incorrect username or password",
                "wrong password",
                "invalid username",
                "incorrect password",
                "no account",
                "doesn't match",
                "username and password",
                "try again",
            ]
            error_in_page = any(kw in page_text.lower() for kw in error_keywords)

            if error_texts or error_in_page:
                err_msg = error_texts[0] if error_texts else "Incorrect credentials"
                return {
                    "success": False,
                    "message": f"❌ Spotify login failed — {err_msg}",
                    "details": "Please check your email and password.",
                }

            # 2. Check for CAPTCHA
            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA appeared! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            # 3. Check for 2FA
            if any(x in page_text.lower() for x in ["two-factor", "2fa", "verify your", "verification code", "enter the code", "confirm your identity"]):
                await progress_cb(
                    "🔐 2FA detected! Please complete manually.\n"
                    "Waiting up to 5 minutes..."
                )
                try:
                    await page.wait_for_function(
                        "() => !window.location.href.toLowerCase().includes('/login')",
                        timeout=300000,
                    )
                    await asyncio.sleep(2)
                    current_url = page.url
                    current_url_lower = current_url.lower()
                except Exception:
                    return {"success": False, "message": "2FA/verification timed out"}

            # 4. STRICT SUCCESS CHECK — URL must have left /login AND sp_dc cookie must exist
            if "/login" in current_url_lower and "accounts.spotify.com/login" in current_url_lower:
                return {
                    "success": False,
                    "message": "❌ Spotify login failed — still on login page",
                    "details": "Please double-check your email and password.",
                }

            # Verify Spotify auth cookie is actually present
            cookies = await context.cookies()
            sp_dc = next((c for c in cookies if c.get("name") == "sp_dc"), None)

            if not sp_dc:
                return {
                    "success": False,
                    "message": "❌ Spotify login failed — no auth session created",
                    "details": "Credentials may be incorrect, or Spotify requires verification.",
                }

            # All checks passed — genuinely authenticated
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
