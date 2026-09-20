"""
H&M Client — browser automation for account creation, login, and Spotify code retrieval.

Uses only official H&M website interfaces. Pauses on CAPTCHA — never bypasses.
Selectors are based on the H&M website structure and may need calibration
if H&M updates their HTML. Errors are reported clearly.
"""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Type alias for progress callback: async function that sends updates to Telegram
ProgressCallback = Callable[[str], Awaitable[None]]


class HMClient:
    """Automates H&M official website for personal account management."""

    def __init__(self, browser_mgr, db, cred_mgr):
        self.browser = browser_mgr
        self.db = db
        self.cred = cred_mgr

    def _get_urls(self, region: str) -> dict:
        """Build H&M URLs for the given region."""
        base = self.browser.db and "https://www2.hm.com" or "https://www2.hm.com"
        return {
            "register": f"{base}/{region}/member/register.html",
            "login": f"{base}/{region}/member/signin.html",
            "profile": f"{base}/{region}/member/my-account/account-overview.html",
            "home": f"{base}/{region}/index.html",
        }

    # ── Account Creation ──────────────────────────────────────

    async def create_account(
        self,
        email: str,
        password: str,
        region: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """
        Create an H&M account via the official registration page.
        Returns dict with keys: success, message, details
        """
        urls = self._get_urls(region)
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening H&M registration page...")
            context = await self.browser.get_context("hm")
            page = await context.new_page()

            # Navigate to registration
            await page.goto(urls["register"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Check for CAPTCHA before proceeding
            if await self.browser.detect_captcha(page):
                await progress_cb(
                    "🛡️ CAPTCHA detected on registration page!\n\n"
                    "Please complete the CAPTCHA manually in your browser.\n"
                    "The bot will wait up to 5 minutes..."
                )
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {
                        "success": False,
                        "message": "CAPTCHA resolution timed out",
                        "details": "Please try again later",
                    }

            await progress_cb("📝 Filling registration form...")

            # Try multiple selector strategies for the email field
            email_selectors = [
                "input[name='email']",
                "input[type='email']",
                "#email",
                "input[data-testid='email-input']",
                "input[placeholder*='email' i]",
                "input[placeholder*='e-mail' i]",
            ]
            email_filled = False
            for sel in email_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await el.fill(email)
                        email_filled = True
                        break
                except Exception:
                    continue

            if not email_filled:
                return {
                    "success": False,
                    "message": "Could not find email field on registration page",
                    "details": "H&M may have updated their website layout. Please register manually.",
                }

            # Fill password field
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "#password",
                "input[data-testid='password-input']",
            ]
            password_filled = False
            for sel in password_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await el.fill(password)
                        password_filled = True
                        break
                except Exception:
                    continue

            if not password_filled:
                return {
                    "success": False,
                    "message": "Could not find password field on registration page",
                    "details": "H&M may have updated their website layout. Please register manually.",
                }

            # Handle terms/consent checkboxes if present
            consent_selectors = [
                "input[name*='terms']",
                "input[name*='consent']",
                "input[name*='agreement']",
                "input[type='checkbox'][required]",
                "label[for*='terms'] input[type='checkbox']",
                "[data-testid*='terms'] input[type='checkbox']",
            ]
            for sel in consent_selectors:
                try:
                    checkboxes = await page.query_selector_all(sel)
                    for cb in checkboxes:
                        if await cb.is_visible() and not await cb.is_checked():
                            await cb.check()
                            await asyncio.sleep(0.3)
                except Exception:
                    continue

            await progress_cb("✅ Form filled. Submitting registration...")

            # Check for CAPTCHA again before submit
            if await self.browser.detect_captcha(page):
                await progress_cb(
                    "🛡️ CAPTCHA appeared before submission!\n\n"
                    "Please complete it manually. Waiting up to 5 minutes..."
                )
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {
                        "success": False,
                        "message": "CAPTCHA resolution timed out",
                        "details": "Please try again later",
                    }

            # Click submit/register button
            submit_selectors = [
                "button[type='submit']",
                "button[data-testid*='register']",
                "button[data-testid*='signup']",
                "input[type='submit']",
                "button:has-text('Register')",
                "button:has-text('Sign up')",
                "button:has-text('Create account')",
                "button:has-text('Join')",
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                return {
                    "success": False,
                    "message": "Could not find submit button",
                    "details": "Please complete registration manually on the H&M website.",
                }

            await asyncio.sleep(3)

            # Check for CAPTCHA after submit
            if await self.browser.detect_captcha(page):
                await progress_cb(
                    "🛡️ CAPTCHA appeared after submission!\n\n"
                    "Please complete it manually. Waiting up to 5 minutes..."
                )
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {
                        "success": False,
                        "message": "CAPTCHA resolution timed out after submission",
                        "details": "Please try again later",
                    }

            # Analyze result page
            page_content = await page.content()
            current_url = page.url.lower()

            # Check for common error indicators
            error_texts = [
                "already registered",
                "already exists",
                "already have an account",
                "email is taken",
                "try logging in",
            ]
            for err in error_texts:
                if err in page_content.lower():
                    return {
                        "success": False,
                        "message": "Email already registered with H&M",
                        "details": "This email already has an H&M account. Try logging in instead.",
                    }

            # Check for email verification requirement
            verify_texts = [
                "verify your email",
                "confirmation email",
                "check your inbox",
                "verification link",
                "activate your account",
            ]
            for vt in verify_texts:
                if vt in page_content.lower():
                    await self.browser.save_session("hm", context)
                    # Save account to database
                    email_enc = self.cred.encrypt(email)
                    pass_enc = self.cred.encrypt(password)
                    await self.db.save_account(email_enc, pass_enc, "hm", "pending_verification", region)
                    await self.db.log_operation("hm_create", "pending_verification", f"Email verification required for {email}")

                    return {
                        "success": True,
                        "message": "📧 Account created — email verification required",
                        "details": (
                            "Please check your inbox and click the verification link.\n"
                            "After verifying, you can use the bot to login."
                        ),
                        "email": email,
                    }

            # Check if we landed on a success/account page
            success_indicators = [
                "my-account",
                "account-overview",
                "welcome",
                "member",
                "dashboard",
            ]
            if any(ind in current_url for ind in success_indicators):
                await self.browser.save_session("hm", context)
                email_enc = self.cred.encrypt(email)
                pass_enc = self.cred.encrypt(password)
                await self.db.save_account(email_enc, pass_enc, "hm", "active", region)
                await self.db.log_operation("hm_create", "success", f"Account created for {email}")

                return {
                    "success": True,
                    "message": "✅ H&M account created successfully!",
                    "details": "Account is active and session saved.",
                    "email": email,
                }

            # Ambiguous result — save what we have and report
            await self.browser.save_session("hm", context)
            email_enc = self.cred.encrypt(email)
            pass_enc = self.cred.encrypt(password)
            await self.db.save_account(email_enc, pass_enc, "hm", "unknown", region)
            await self.db.log_operation("hm_create", "unknown", f"Registration result unclear for {email}")

            return {
                "success": True,
                "message": "⚠️ Registration submitted — please verify manually",
                "details": (
                    "The form was submitted but the result is ambiguous.\n"
                    "Please check your email or log into H&M to confirm."
                ),
                "email": email,
            }

        except Exception as e:
            logger.error(f"H&M registration error: {e}", exc_info=True)
            await self.db.log_operation("hm_create", "error", str(e))
            return {
                "success": False,
                "message": f"❌ Registration failed: {type(e).__name__}",
                "details": str(e),
            }
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
        region: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """Log into H&M with credentials. Saves session on success."""
        urls = self._get_urls(region)
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening H&M login page...")
            context = await self.browser.get_context("hm")
            page = await context.new_page()

            await page.goto(urls["login"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            await progress_cb("🔑 Entering credentials...")

            # Fill email
            for sel in ["input[name='email']", "input[type='email']", "#email", "input[name='username']"]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(email)
                        break
                except Exception:
                    continue

            # Fill password
            for sel in ["input[name='password']", "input[type='password']", "#password"]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.fill(password)
                        break
                except Exception:
                    continue

            # Submit
            for sel in ["button[type='submit']", "button:has-text('Sign in')", "button:has-text('Log in')"]:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        break
                except Exception:
                    continue

            await asyncio.sleep(3)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA appeared! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            current_url = page.url.lower()
            if any(x in current_url for x in ["my-account", "account-overview", "member"]):
                await self.browser.save_session("hm", context)
                await self.db.log_operation("hm_login", "success", f"Logged in as {email}")
                return {
                    "success": True,
                    "message": "✅ Logged into H&M successfully!",
                    "email": email,
                }

            page_content = await page.content()
            if any(x in page_content.lower() for x in ["incorrect", "wrong password", "invalid"]):
                return {
                    "success": False,
                    "message": "❌ Login failed — incorrect credentials",
                    "details": "Please check your email and password.",
                }

            # Might still be on login page with errors
            await self.browser.save_session("hm", context)
            await self.db.log_operation("hm_login", "unknown", "Login result unclear")
            return {
                "success": True,
                "message": "⚠️ Login submitted — please verify manually",
            }

        except Exception as e:
            logger.error(f"H&M login error: {e}", exc_info=True)
            return {"success": False, "message": f"❌ Login failed: {e}"}
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    # ── Get Spotify Code ──────────────────────────────────────

    async def get_spotify_code(
        self,
        region: str,
        progress_cb: ProgressCallback,
    ) -> dict:
        """
        Navigate to H&M profile and retrieve any available Spotify voucher/redeem code.
        Uses only the authenticated H&M session — no hidden endpoints.
        """
        urls = self._get_urls(region)
        context = None
        page = None

        try:
            await progress_cb("🌐 Opening H&M profile page...")
            context = await self.browser.get_context("hm")
            page = await context.new_page()

            await page.goto(urls["profile"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Check if we're redirected to login (session expired)
            if "signin" in page.url.lower() or "login" in page.url.lower():
                return {
                    "success": False,
                    "message": "🔑 H&M session expired — login required",
                    "details": "Please use Create H&M Account or login first.",
                    "need_login": True,
                }

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out"}

            await progress_cb("🔍 Looking for Spotify offers in profile...")

            # Look for Spotify-related sections/links
            spotify_selectors = [
                "a[href*='spotify']",
                "[class*='spotify' i]",
                "[data-testid*='spotify' i]",
                "a:has-text('Spotify')",
                "button:has-text('Spotify')",
                "[class*='offer' i] a",
                "[class*='reward' i] a",
                "[class*='voucher' i]",
                "[class*='benefit' i]",
            ]

            spotify_element = None
            for sel in spotify_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        spotify_element = el
                        break
                except Exception:
                    continue

            if spotify_element:
                await progress_cb("🎵 Found Spotify section! Opening...")
                await spotify_element.click()
                await asyncio.sleep(3)

                if await self.browser.detect_captcha(page):
                    await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                    await self.browser.wait_for_captcha_resolution(page)

            # Try to find a code on the page
            code_selectors = [
                "[class*='code' i]",
                "[class*='voucher' i]",
                "[class*='redeem' i]",
                "[class*='coupon' i]",
                "[data-testid*='code' i]",
                "input[readonly]",
                "code",
                ".promo-code",
                ".voucher-code",
            ]

            page_text = await page.inner_text("body")

            # Search for code patterns (typically alphanumeric, 10-30 chars)
            import re
            code_patterns = [
                r'(?:code|voucher|redeem|coupon)[:\s]*([A-Z0-9]{8,30})',
                r'([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})',
                r'([A-Z0-9]{10,30})',
            ]

            found_code = None
            for sel in code_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if text and len(text) >= 8 and text.replace("-", "").isalnum():
                            found_code = text
                            break
                except Exception:
                    continue

            if not found_code:
                for pattern in code_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        found_code = match.group(1)
                        break

            if found_code:
                # Save the code encrypted
                code_enc = self.cred.encrypt(found_code)
                await self.db.save_spotify_code(code_enc)
                await self.browser.save_session("hm", context)
                await self.db.log_operation("get_spotify_code", "success", "Code retrieved")

                return {
                    "success": True,
                    "message": "🎵 Spotify code found!",
                    "code": found_code,
                }
            else:
                await self.browser.save_session("hm", context)
                await self.db.log_operation("get_spotify_code", "not_found", "No code available")

                return {
                    "success": False,
                    "message": "ℹ️ No Spotify code found in your H&M profile",
                    "details": (
                        "Possible reasons:\n"
                        "• No active Spotify offer for your account\n"
                        "• Offer has expired or already been claimed\n"
                        "• The offer is in a different section\n\n"
                        "Try checking your H&M profile manually."
                    ),
                }

        except Exception as e:
            logger.error(f"Spotify code retrieval error: {e}", exc_info=True)
            await self.db.log_operation("get_spotify_code", "error", str(e))
            return {
                "success": False,
                "message": f"❌ Failed to retrieve Spotify code: {type(e).__name__}",
                "details": str(e),
            }
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
