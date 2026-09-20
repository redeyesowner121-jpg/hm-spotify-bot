"""
Browser module — Playwright async browser lifecycle, session management, CAPTCHA detection.
Never bypasses CAPTCHA or security mechanisms — only detects and pauses.
"""

import json
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

# Selectors that indicate a CAPTCHA or security challenge is present.
# The bot will PAUSE (never bypass) when any of these are detected.
CAPTCHA_INDICATORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "#captcha",
    ".g-recaptcha",
    ".h-captcha",
    "[data-sitekey]",
    "[class*='captcha']",
    "[id*='captcha']",
    "#challenge-running",
    "#cf-challenge-running",
]


class BrowserManager:
    """Manages a shared Playwright browser instance with encrypted session storage."""

    def __init__(self, headless: bool, db, cred_mgr):
        self.headless = headless
        self.db = db
        self.cred_mgr = cred_mgr
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def initialize(self):
        """Launch the Playwright browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.info(f"Browser launched (headless={self.headless})")

    async def get_context(self, service: str) -> BrowserContext:
        """
        Create a new browser context, restoring saved session cookies if available.
        Returns a fresh context with a realistic user-agent.
        """
        if not self._browser:
            raise RuntimeError("Browser not initialized — call initialize() first")

        storage_state = None
        session_enc = await self.db.get_session(service)
        if session_enc:
            try:
                storage_state = json.loads(self.cred_mgr.decrypt(session_enc))
                logger.info(f"Restored saved session for '{service}'")
            except Exception as e:
                logger.warning(f"Failed to restore session for '{service}': {e}")
                storage_state = None

        context = await self._browser.new_context(
            storage_state=storage_state,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        return context

    async def save_session(self, service: str, context: BrowserContext):
        """Encrypt and persist the browser context's storage state."""
        try:
            state = await context.storage_state()
            encrypted = self.cred_mgr.encrypt(json.dumps(state))
            await self.db.save_session(service, encrypted)
            logger.info(f"Session saved for '{service}'")
        except Exception as e:
            logger.error(f"Failed to save session for '{service}': {e}")

    async def clear_session(self, service: str):
        """Remove saved session for a service."""
        await self.db.clear_session(service)
        logger.info(f"Session cleared for '{service}'")

    async def detect_captcha(self, page: Page) -> bool:
        """
        Check if a CAPTCHA or security challenge is visible on the page.
        Returns True if detected — the caller should PAUSE and notify the user.
        This method NEVER attempts to solve or bypass any challenge.
        """
        for selector in CAPTCHA_INDICATORS:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.info(f"🛡️ CAPTCHA/challenge detected: {selector}")
                    return True
            except Exception:
                continue
        return False

    async def wait_for_captcha_resolution(self, page: Page, timeout_ms: int = 300000):
        """
        Wait for the user to manually resolve a CAPTCHA.
        Polls every 3 seconds for up to `timeout_ms` (default 5 min).
        Returns True if CAPTCHA was resolved, False if timed out.
        """
        import asyncio

        elapsed = 0
        interval = 3000
        while elapsed < timeout_ms:
            if not await self.detect_captcha(page):
                logger.info("CAPTCHA resolved by user")
                return True
            await asyncio.sleep(interval / 1000)
            elapsed += interval
        logger.warning("CAPTCHA resolution timed out")
        return False

    async def close(self):
        """Shut down browser and Playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser shut down")
