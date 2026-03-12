import json
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from backend.config import settings
from backend.scraper.anti_detect import apply_stealth
from backend.db.database import db
from backend.db.models import Session
from backend.db import crud

logger = logging.getLogger(__name__)

# Realistic Chrome 131 on macOS User-Agent
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.6778.86 Safari/537.36"
)


class ScraperEngine:
    """Manages a single Playwright Chromium browser instance."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._captcha_active: bool = False

    @property
    def captcha_active(self) -> bool:
        return self._captcha_active

    @captcha_active.setter
    def captcha_active(self, val: bool):
        self._captcha_active = val

    async def start(self):
        """Start browser with persistent context and anti-detection."""
        settings.ensure_dirs()
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=settings.HEADLESS,
            args=[
                # Core anti-automation detection
                "--disable-blink-features=AutomationControlled",
                # Remove automation infobar
                "--disable-infobars",
                # Disable various automation flags
                "--disable-dev-shm-usage",
                "--disable-ipc-flooding-protection",
                # Performance
                "--no-first-run",
                "--no-default-browser-check",
                "--no-sandbox",
                # Pretend to be normal browser
                "--disable-features=TranslateUI",
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
                # Window size
                "--window-size=1280,720",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=CHROME_UA,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            color_scheme="light",
            # Pretend to accept webp/avif images
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
        )

        await apply_stealth(self._context)

        # Try to load saved cookies
        try:
            await self.load_cookies("default")
            logger.info("Loaded saved cookies")
        except Exception:
            logger.info("No saved cookies found, starting fresh")

    async def stop(self):
        """Save cookies and close browser."""
        try:
            await self.save_cookies("default")
        except Exception as e:
            logger.warning(f"Failed to save cookies on shutdown: {e}")

        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def get_page(self) -> Page:
        """Get an available page, reusing existing or creating new."""
        if self._context is None:
            raise RuntimeError("Engine not started")

        pages = self._context.pages
        if pages:
            return pages[0]

        page = await self._context.new_page()
        return page

    async def new_page(self) -> Page:
        """Always create a new page/tab."""
        if self._context is None:
            raise RuntimeError("Engine not started")
        return await self._context.new_page()

    async def save_cookies(self, name: str = "default"):
        """Save current browser cookies to DB."""
        if self._context is None:
            return
        cookies = await self._context.cookies()
        session = Session(
            name=name,
            cookies=json.dumps(cookies, ensure_ascii=False),
            user_agent=CHROME_UA,
        )
        await crud.save_session(session)
        logger.info(f"Saved {len(cookies)} cookies as '{name}'")

    async def load_cookies(self, name: str = "default"):
        """Load cookies from DB into browser context."""
        if self._context is None:
            return
        session = await crud.get_session(name)
        if session is None:
            raise ValueError(f"No session found with name '{name}'")
        cookies = json.loads(session.cookies)
        await self._context.add_cookies(cookies)
        logger.info(f"Loaded {len(cookies)} cookies from '{name}'")

    async def check_login(self) -> bool:
        """Check if currently logged in to Douyin by verifying cookies are valid."""
        if self._context is None:
            return False

        cookies = await self._context.cookies(settings.DOUYIN_BASE_URL)
        cookie_names = {c["name"] for c in cookies}
        if "sessionid" not in cookie_names:
            return False

        for c in cookies:
            if c["name"] == "sessionid":
                if not c.get("value"):
                    return False
                if c.get("expires", -1) > 0:
                    import time
                    if c["expires"] < time.time():
                        logger.info("sessionid cookie expired")
                        return False
                return True

        return False

    async def detect_captcha(self, page: Page) -> bool:
        """Check if a CAPTCHA/verification is shown on the page."""
        try:
            captcha = await page.query_selector(
                ", ".join([
                    "[class*='captcha']",
                    "[class*='verify']",
                    "[class*='secsdk']",
                    "#captcha_container",
                    ".secsdk-captcha-drag-icon",
                    "[class*='captcha-verify']",
                    "div[id*='captcha']",
                    "[class*='slider']",
                ])
            )
            is_active = captcha is not None
            if is_active and not self._captcha_active:
                logger.warning("CAPTCHA detected! Please solve it manually in the browser.")
            self._captcha_active = is_active
            return is_active
        except Exception:
            return False

    async def wait_for_captcha_resolve(self, page: Page, timeout: int = 180) -> bool:
        """Wait for captcha to be resolved, returns True if resolved."""
        if not await self.detect_captcha(page):
            return True

        logger.warning(f"Waiting for CAPTCHA resolution (timeout: {timeout}s)...")
        for i in range(timeout):
            await page.wait_for_timeout(1000)
            if not await self.detect_captcha(page):
                logger.info("CAPTCHA resolved!")
                self._captcha_active = False
                return True
            if i % 30 == 0 and i > 0:
                logger.info(f"Still waiting for CAPTCHA... ({i}s elapsed)")

        logger.error("CAPTCHA timeout")
        self._captcha_active = False
        return False

    async def safe_goto(self, page: Page, url: str, **kwargs) -> bool:
        """Navigate to URL and handle captcha if it appears.
        Returns True if page loaded successfully (captcha resolved or not present).
        """
        kwargs.setdefault("wait_until", "domcontentloaded")
        await page.goto(url, **kwargs)

        # Brief wait for captcha to potentially appear
        await page.wait_for_timeout(2000)

        if await self.detect_captcha(page):
            resolved = await self.wait_for_captcha_resolve(page)
            if not resolved:
                return False

        return True

    async def wait_for_login(self) -> bool:
        """Navigate to Douyin and wait for user to scan QR code."""
        page = await self.get_page()
        await page.goto(settings.DOUYIN_BASE_URL, wait_until="domcontentloaded")
        logger.info("Please scan the QR code to login...")

        for _ in range(120):
            await page.wait_for_timeout(1000)
            if await self.check_login():
                valid = await self._verify_login_on_page(page)
                if valid:
                    await self.save_cookies("default")
                    logger.info("Login successful and verified!")
                    return True
                else:
                    logger.info("Cookies found, verifying login on page...")
        logger.warning("Login timeout")
        return False

    async def _verify_login_on_page(self, page) -> bool:
        """Verify login by checking the page for logged-in indicators."""
        try:
            cookies = await self._context.cookies(settings.DOUYIN_BASE_URL)
            for c in cookies:
                if c["name"] == "sessionid" and c.get("value"):
                    logged_in = await page.evaluate("""
                        () => {
                            const avatar = document.querySelector('[data-e2e="user-info"] img, .avatar-wrapper img, [class*="avatar"] img');
                            const loginBtn = document.querySelector('[class*="login-guide"]');
                            return !!(avatar || !loginBtn);
                        }
                    """)
                    if logged_in:
                        return True
                    if len(c["value"]) > 10:
                        logger.info("sessionid cookie looks valid (length=%d), accepting", len(c["value"]))
                        return True
            return False
        except Exception as e:
            logger.warning("Page verification error: %s", e)
            cookies = await self._context.cookies(settings.DOUYIN_BASE_URL)
            for c in cookies:
                if c["name"] == "sessionid" and c.get("value") and len(c["value"]) > 10:
                    return True
            return False

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Engine not started")
        return self._context


# Global singleton
engine = ScraperEngine()
