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

            # Navigate directly to register page or signin page
            try:
                await page.goto(urls["register"], wait_until="domcontentloaded", timeout=30000)
            except Exception:
                await page.goto(urls["login"], wait_until="domcontentloaded", timeout=30000)

            await asyncio.sleep(3)

            # Accept cookies if the popup appears (often blocks profile button)
            try:
                cookie_btn = await page.query_selector("button#onetrust-accept-btn-handler")
                if cookie_btn and await cookie_btn.is_visible():
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Click profile/sign-in button in top right or navigate to signin URL directly if needed
            await progress_cb("👤 Accessing profile/sign-in menu...")
            profile_selectors = [
                "button[data-testid='myAccount']",
                "a[data-testid='myAccount']",
                ".menu__myhm",
                "a[href*='signin']",
                "a[href*='login']",
                ".account-link",
                "button:has-text('Sign in')",
                "a:has-text('Sign in')",
                "button:has-text('My Account')",
                "a:has-text('My Account')"
            ]
            clicked_profile = False
            for sel in profile_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        clicked_profile = True
                        break
                except Exception:
                    continue

            if not clicked_profile:
                # Direct navigation fallback to signin URL
                try:
                    await page.goto(urls["login"], wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    pass

            await asyncio.sleep(4)

            # Check for CAPTCHA
            if await self.browser.detect_captcha(page):
                await progress_cb(
                    "🛡️ CAPTCHA detected!\n\n"
                    "Please complete it manually. Waiting up to 5 minutes..."
                )
                resolved = await self.browser.wait_for_captcha_resolution(page)
                if not resolved:
                    return {"success": False, "message": "CAPTCHA resolution timed out", "details": "Try again later"}

            await progress_cb("📝 Entering details to initiate registration...")

            # If there is a tab for "Register" / "Become a member" / "Create account", click it
            for reg_tab_sel in [
                "button:has-text('Register')",
                "button:has-text('Become a member')",
                "button:has-text('Create account')",
                "a:has-text('Register')",
                "a:has-text('Become a member')",
                "[data-testid*='register']",
            ]:
                try:
                    rtab = await page.query_selector(reg_tab_sel)
                    if rtab and await rtab.is_visible():
                        await rtab.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            # Try multiple selector strategies for the email field
            email_selectors = [
                "input[name='email']",
                "input[type='email']",
                "#email",
                "input[id*='email' i]",
                "input[data-testid='email-input']",
                "input[placeholder*='email' i]",
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
                "input[id*='password' i]",
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

            # Fill extra fields: First Name & Date of Birth if requested/present
            # 1. First Name / Name
            name_selectors = [
                "input[name='firstName']",
                "input[name='first_name']",
                "input[name='name']",
                "input[id*='firstName' i]",
                "input[placeholder*='First Name' i]",
                "input[placeholder*='Name' i]",
            ]
            first_name = email.split("@")[0]
            for sel in name_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await el.fill(first_name)
                        break
                except Exception:
                    continue

            # 2. Date of Birth (e.g. DD/MM/YYYY or separate fields or input[type='date'])
            dob_selectors = [
                "input[name='dateOfBirth']",
                "input[name='dob']",
                "input[name='birthdate']",
                "input[id*='dob' i]",
                "input[placeholder*='DD/MM/YYYY' i]",
                "input[placeholder*='YYYY-MM-DD' i]",
            ]
            for sel in dob_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await el.fill("01/01/1998")
                        break
                except Exception:
                    continue

            # Handle terms/consent/agreement checkboxes ("I agree")
            consent_selectors = [
                "input[name*='terms']",
                "input[name*='consent']",
                "input[name*='agreement']",
                "input[type='checkbox']",
                "label[for*='terms']",
                "label[for*='agree']",
                "[data-testid*='terms']",
                "[data-testid*='agree']",
            ]
            for sel in consent_selectors:
                try:
                    checkboxes = await page.query_selector_all(sel)
                    for cb in checkboxes:
                        if await cb.is_visible():
                            if cb.tag_name == "LABEL":
                                await cb.click()
                            elif not await cb.is_checked():
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
                email_enc = self.cred.encrypt(email)
                pass_enc = self.cred.encrypt(password)
                await self.db.save_account(email_enc, pass_enc, "hm", "active", region)
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

            await progress_cb("🔍 Looking for Spotify offer in your H&M profile...")
            await asyncio.sleep(2)

            # Dismiss cookie banner if it exists
            try:
                cookie_btn = await page.query_selector("button#onetrust-accept-btn-handler")
                if cookie_btn and await cookie_btn.is_visible():
                    await cookie_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Scroll down to ensure lazy-loaded offers appear
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(2)

            # Search specifically for the offer text described by user:
            # "Free 2-month trial | Spotify Premium Standard offer" or "Free 3-month trial | Spotify Premium Standard offer"
            spotify_offer_selectors = [
                "text=/Free [23]-month trial.*Spotify/i",
                "text=/Spotify Premium Standard offer/i",
                "text=/Spotify Premium/i",
                "[data-testid*='offer']:has-text('Spotify')",
                "[class*='offer']:has-text('Spotify')",
                "[class*='reward']:has-text('Spotify')",
                "a:has-text('Spotify')",
                "button:has-text('Spotify')",
                "div:has-text('Spotify Premium')",
                "h3:has-text('Spotify')",
                "h4:has-text('Spotify')",
                "p:has-text('Spotify')",
            ]

            spotify_element = None
            for sel in spotify_offer_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        spotify_element = el
                        break
                except Exception:
                    continue

            # If not found on initial screen, check for an "Offers", "My Offers", or "Rewards" tab
            if not spotify_element:
                await progress_cb("📑 Checking 'Offers & Rewards' section...")
                tab_selectors = [
                    "a[href*='offers']",
                    "a[href*='rewards']",
                    "button:has-text('Offers')",
                    "a:has-text('Offers')",
                    "button:has-text('Rewards')",
                    "a:has-text('Rewards')",
                    "button:has-text('Benefits')",
                    "a:has-text('Benefits')",
                ]
                for tsel in tab_selectors:
                    try:
                        tab_el = await page.query_selector(tsel)
                        if tab_el and await tab_el.is_visible():
                            await tab_el.click()
                            await asyncio.sleep(3)
                            break
                    except Exception:
                        continue

                # Try finding offer again after navigating tab
                for sel in spotify_offer_selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el and await el.is_visible():
                            spotify_element = el
                            break
                    except Exception:
                        continue

            if not spotify_element:
                await self.browser.save_session("hm", context)
                await self.db.log_operation("get_spotify_code", "not_found", "Offer not found on profile")
                return {
                    "success": False,
                    "message": "ℹ️ 'Spotify Premium Standard offer' not found on your profile",
                    "details": (
                        "We searched for:\n"
                        "• Free 2-month trial | Spotify Premium Standard offer\n"
                        "• Free 3-month trial | Spotify Premium Standard offer\n\n"
                        "Please verify your H&M account has active Spotify membership benefits."
                    ),
                }

            await progress_cb("🎵 Found Spotify offer! Opening offer details...")
            await spotify_element.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            await spotify_element.click()
            await asyncio.sleep(3)

            if await self.browser.detect_captcha(page):
                await progress_cb("🛡️ CAPTCHA detected! Please complete manually. Waiting...")
                await self.browser.wait_for_captcha_resolution(page)

            # Scroll down to reveal the Redeem button
            await progress_cb("📜 Scrolling down to find the Redeem button...")
            await page.evaluate("window.scrollBy(0, 800)")
            # Also scroll any active modal / drawer dialog
            try:
                modals = await page.query_selector_all("[role='dialog'], [class*='modal'], [class*='drawer'], [class*='sheet']")
                for m in modals:
                    if await m.is_visible():
                        await m.evaluate("el => el.scrollTop = el.scrollHeight")
            except Exception:
                pass
            await asyncio.sleep(2)

            # Look for Redeem button
            redeem_selectors = [
                "button:has-text('Redeem')",
                "a:has-text('Redeem')",
                "button:has-text('Claim')",
                "a:has-text('Claim')",
                "[data-testid*='redeem']",
                "[data-testid*='claim']",
                "button:has-text('Get code')",
                "a:has-text('Get code')",
                "button:has-text('Go to offer')",
                "a:has-text('Go to offer')",
            ]

            redeem_btn = None
            for rsel in redeem_selectors:
                try:
                    btn = await page.query_selector(rsel)
                    if btn and await btn.is_visible():
                        redeem_btn = btn
                        break
                except Exception:
                    continue

            redeem_url = None
            extracted_code = None
            captured_spotify_urls = []

            # Listen to all network requests to catch Spotify redirect URLs
            def on_request(req):
                if "spotify.com" in req.url.lower():
                    captured_spotify_urls.append(req.url)

            page.on("request", on_request)

            if redeem_btn:
                await progress_cb("🎁 Found Redeem button! Clicking to get redeem link...")
                await redeem_btn.scroll_into_view_if_needed()

                # Check direct href or data attributes on button
                for attr in ["href", "data-href", "data-url", "data-link"]:
                    val = await redeem_btn.get_attribute(attr)
                    if val and ("spotify" in val or "http" in val):
                        redeem_url = val
                        break

                # Click and catch navigation or new tab
                try:
                    async with context.expect_page(timeout=10000) as page_info:
                        await redeem_btn.click()
                    new_tab = await page_info.value
                    await new_tab.wait_for_load_state("domcontentloaded", timeout=15000)
                    await asyncio.sleep(3)
                    if "spotify" in new_tab.url.lower():
                        redeem_url = new_tab.url
                except Exception:
                    # Same tab navigation or redirect
                    await asyncio.sleep(5)
                    if "spotify" in page.url.lower():
                        redeem_url = page.url

            # Fallback 1: check all open tabs in browser context
            if not redeem_url or "hm.com" in redeem_url:
                for p in context.pages:
                    if "spotify.com" in p.url.lower():
                        redeem_url = p.url
                        break

            # Fallback 2: check captured network requests
            if not redeem_url and captured_spotify_urls:
                for u in reversed(captured_spotify_urls):
                    if any(x in u.lower() for x in ["redeem", "claim", "purchase", "spotify.com"]):
                        redeem_url = u
                        break

            # Fallback 3: scan HTML content for any Spotify URL
            if not redeem_url:
                import re
                page_content = await page.content()
                url_match = re.search(r'https?://[^\s"\'<>]+spotify\.com[^\s"\'<>]*', page_content)
                if url_match:
                    redeem_url = url_match.group(0)

            # Blacklist of junk words/paths — for BOTH URL and code validation
            JUNK_WORDS = {
                "permission", "subscribe", "standard", "undefined", "membership",
                "overview", "benefit", "voucher", "account", "settings", "profile",
                "details", "password", "continue", "register", "redeem", "cancel",
                "cookie", "accept", "submit", "button", "trial", "month", "months",
                "login", "signup", "logout", "privacy", "terms", "help", "support",
                "home", "index", "about", "contact", "error", "page",
            }

            # Validate redeem_url — MUST be a real Spotify URL (not H&M internal links)
            if redeem_url:
                url_lower = redeem_url.lower()
                if "spotify.com" not in url_lower:
                    logger.warning(f"Discarding non-Spotify redeem_url: {redeem_url}")
                    redeem_url = None
                else:
                    # Reject if last URL path segment is a junk word
                    import urllib.parse
                    path = urllib.parse.urlparse(redeem_url).path.rstrip("/")
                    last_segment = path.split("/")[-1].lower()
                    if last_segment in JUNK_WORDS:
                        logger.warning(f"Discarding junk Spotify URL segment '{last_segment}': {redeem_url}")
                        redeem_url = None

            # Extract voucher code from inside redeem_url if it's valid
            if redeem_url:
                code_match = re.search(r'(?:code|voucher|token|coupon)=([A-Za-z0-9_\-]{6,30})', redeem_url, re.IGNORECASE)
                if not code_match:
                    # /redeem/XXXXX — only if XXXXX looks like a real code (has digits or mixed chars)
                    code_match = re.search(r'/(?:redeem|claim|voucher)/([A-Za-z0-9_\-]{6,30})', redeem_url, re.IGNORECASE)
                if code_match:
                    candidate = code_match.group(1)
                    if candidate.lower() not in JUNK_WORDS and (any(c.isdigit() for c in candidate) or not candidate.isalpha()):
                        extracted_code = candidate

            # Validate extracted_code — must be 6–30 chars, alphanumeric, NOT a junk word, has digits or is mixed case
            if extracted_code:
                c = extracted_code.strip()
                is_real_code = (
                    6 <= len(c) <= 30
                    and c.lower() not in JUNK_WORDS
                    and re.match(r'^[A-Za-z0-9_\-]+$', c)
                    and (any(ch.isdigit() for ch in c) or not c.isalpha())
                )
                if not is_real_code:
                    logger.warning(f"Discarding junk extracted_code: {c}")
                    extracted_code = None

            # Prioritize the full Spotify redeem_url, fallback to bare code
            code_to_save = redeem_url or extracted_code

            # If we got a redeem_url or code:
            if code_to_save:
                code_enc = self.cred.encrypt(code_to_save)
                await self.db.save_spotify_code(code_enc)
                await self.browser.save_session("hm", context)
                await self.db.log_operation("get_spotify_code", "success", code_to_save)

                return {
                    "success": True,
                    "message": "🎉 Spotify Redeem Link Retrieved!",
                    "redeem_url": redeem_url,
                    "code": extracted_code,
                }
            else:
                await self.browser.save_session("hm", context)
                await self.db.log_operation("get_spotify_code", "not_found", "No redeem link or code found after clicking")
                return {
                    "success": False,
                    "message": "⚠️ Opened offer but could not extract Spotify redeem link",
                    "details": (
                        "The offer was opened, but the Redeem button did not yield a Spotify link.\n"
                        "Please check your H&M profile manually or try again."
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
