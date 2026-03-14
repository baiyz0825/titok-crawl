import asyncio
import base64
import json
import logging
import random
import re
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from backend.config import settings
from backend.scraper.anti_detect import apply_stealth
from backend.scraper.slider_captcha import detect_slider_captcha, solve_slider_captcha
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
        # Page pool: one page per concurrent task
        self._page_pool: dict[int, Page] = {}  # task_id -> Page
        self._page_locks: dict[int, asyncio.Lock] = {}  # task_id -> Lock
        self._pool_lock = asyncio.Lock()  # Protects access to _page_pool and _page_locks

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

    async def acquire_page(self, task_id: int) -> Page:
        """Acquire a page for a specific task.

        Each task gets its own page that is reused for the entire task duration.
        Different tasks use different pages to avoid conflicts.

        Args:
            task_id: Unique identifier for the task (from scheduler)

        Returns:
            Page: A browser page dedicated to this task
        """
        if self._context is None:
            raise RuntimeError("Engine not started")

        async with self._pool_lock:
            # Check if this task already has a page
            if task_id in self._page_pool:
                logger.debug(f"Task #{task_id} reusing existing page")
                return self._page_pool[task_id]

            # Create new page for this task
            page = await self._context.new_page()
            page.set_default_timeout(settings.PAGE_TIMEOUT)

            # Store in pool
            self._page_pool[task_id] = page
            self._page_locks[task_id] = asyncio.Lock()

            logger.info(f"Task #{task_id} assigned new page (total pages: {len(self._page_pool)})")
            return page

    async def release_page(self, task_id: int):
        """Release and close a page for a specific task.

        Should be called when the task is complete to free resources.

        Args:
            task_id: Unique identifier for the task
        """
        async with self._pool_lock:
            if task_id not in self._page_pool:
                logger.warning(f"Task #{task_id} has no page to release")
                return

            page = self._page_pool.pop(task_id)
            self._page_locks.pop(task_id, None)

            try:
                await page.close()
                logger.info(f"Task #{task_id} page closed (remaining pages: {len(self._page_pool)})")
            except Exception as e:
                logger.warning(f"Failed to close page for task #{task_id}: {e}")

    async def get_page(self) -> Page:
        """Legacy method - creates a new page each time.

        Deprecated: Use acquire_page(task_id) instead for proper page pooling.
        """
        if self._context is None:
            raise RuntimeError("Engine not started")

        page = await self._context.new_page()
        page.set_default_timeout(settings.PAGE_TIMEOUT)
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

    async def get_current_user_id(self) -> str | None:
        """Get current logged-in user's sec_user_id from page data."""
        if self._context is None:
            return None

        try:
            page = await self.get_page()

            # Try to get from current page first
            # ✅ 正确路径: window.SSR_RENDER_DATA.app.user.info.secUid
            try:
                sec_user_id = await page.evaluate("""() => {
                    if (window.SSR_RENDER_DATA?.app?.user?.info?.secUid) {
                        return window.SSR_RENDER_DATA.app.user.info.secUid;
                    }
                    return null;
                }""")

                if sec_user_id:
                    logger.info(f"Extracted sec_user_id from page: {sec_user_id}")
                    return sec_user_id
            except Exception as e:
                logger.debug(f"Failed to extract from current page: {e}")

            # If not found on current page, navigate to user/self
            await page.goto(f"{settings.DOUYIN_BASE_URL}/user/self", wait_until="domcontentloaded")
            await asyncio.sleep(2)

            try:
                sec_user_id = await page.evaluate("""() => {
                    if (window.SSR_RENDER_DATA?.app?.user?.info?.secUid) {
                        return window.SSR_RENDER_DATA.app.user.info.secUid;
                    }
                    return null;
                }""")

                if sec_user_id:
                    logger.info(f"Extracted sec_user_id from /user/self: {sec_user_id}")
                    return sec_user_id
            except Exception as e:
                logger.debug(f"Failed to extract from /user/self: {e}")

            logger.warning("Could not extract current sec_user_id")
            return None

        except Exception as e:
            logger.error(f"Failed to get current user ID: {e}")
            return None

    async def detect_captcha(self, page: Page) -> bool:
        """Check if a CAPTCHA/verification is shown on the page."""
        try:
            # Use specific selectors to avoid false positives.
            # Douyin captcha containers are typically full-screen overlays
            # with specific class patterns.
            captcha = await page.query_selector(
                ", ".join([
                    "#captcha_container",
                    ".captcha-verify-container",
                    ".secsdk-captcha-drag-icon",
                    "[class*='captcha-verify'][class*='container']",
                    "[class*='secsdk-captcha']",
                    "div.captcha_verify_container",
                    "#secsdk-captcha-drag-wrapper",
                ])
            )
            if captcha is None:
                if self._captcha_active:
                    logger.info("CAPTCHA element no longer found on page")
                self._captcha_active = False
                return False

            # Extra check: the captcha element must be visible
            is_visible = await captcha.is_visible()
            if not is_visible:
                self._captcha_active = False
                return False

            if not self._captcha_active:
                logger.warning("CAPTCHA detected! Please solve it manually in the browser.")
            self._captcha_active = True
            return True
        except Exception:
            return False

    async def wait_for_captcha_resolve(self, page: Page, timeout: int = 180) -> bool:
        """Wait for captcha to be resolved, returns True if resolved.

        First attempts automatic slider solving, then falls back to
        waiting for manual resolution.
        """
        if not await self.detect_captcha(page):
            return True

        # Try automatic slider captcha solving first
        if await detect_slider_captcha(page):
            logger.info("Attempting automatic slider captcha solve...")
            solved = await solve_slider_captcha(page, max_retries=3)
            if solved:
                logger.info("Slider captcha auto-solved!")
                self._captcha_active = False
                return True
            logger.warning("Auto-solve failed, falling back to manual resolution")

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
        # Random pre-navigation delay to mimic human behavior
        pre_delay = random.uniform(1.0, 3.0)
        await page.wait_for_timeout(int(pre_delay * 1000))

        kwargs.setdefault("wait_until", "domcontentloaded")
        await page.goto(url, **kwargs)

        # Randomized post-navigation wait
        post_delay = random.uniform(1.5, 3.0)
        await page.wait_for_timeout(int(post_delay * 1000))

        if await self.detect_captcha(page):
            resolved = await self.wait_for_captcha_resolve(page)
            if not resolved:
                return False

        return True

    async def wait_for_login(self) -> bool:
        """Navigate to Douyin and wait for user to scan QR code.

        完整流程：
        1. 显示二维码
        2. 等待用户扫码
        3. 自动点击"接收短信验证码"
        4. 等待用户输入验证码
        5. 自动点击"保存登录信息"（如果弹出）
        6. 登录成功
        """
        page = await self.get_page()
        await page.goto(settings.DOUYIN_BASE_URL, wait_until="domcontentloaded")
        logger.info("Please scan the QR code to login...")

        # 跟踪验证窗口状态，防止超时回到扫码状态
        verification_window_seen = False
        verification_window_start_time = None

        for i in range(180):  # 增加到3分钟
            await page.wait_for_timeout(1000)

            # 步骤1: 自动处理"接收短信验证码"弹窗
            if await self._handle_sms_consent_dialog(page):
                logger.info("✅ 已点击'接收短信验证码'")
                verification_window_seen = True
                verification_window_start_time = i

            # 步骤2: 检测验证窗口超时（约2-3分钟）
            if verification_window_seen and verification_window_start_time:
                elapsed = i - verification_window_start_time
                if elapsed > 120:  # 2分钟后检查
                    # 检查是否回到扫码状态
                    qr_visible = await page.query_selector('#animate_qrcode_container')
                    if qr_visible and await qr_visible.is_visible():
                        logger.warning("❌ 验证窗口超时，已回到扫码状态，请重新扫码")
                        verification_window_seen = False
                        verification_window_start_time = None

            # 步骤3: 检查是否登录成功
            if await self.check_login():
                # 步骤4: 自动处理"保存登录信息"对话框
                await self._handle_save_login_dialog(page)

                valid = await self._verify_login_on_page(page)
                if valid:
                    await self.save_cookies("default")
                    logger.info("✅ Login successful and verified!")
                    return True
                else:
                    logger.info("Cookies found, verifying login on page...")

        logger.warning("⏰ Login timeout (3 minutes)")
        return False

    async def _handle_sms_consent_dialog(self, page: Page) -> bool:
        """自动处理短信验证码同意界面

        扫码成功后会弹出身份验证窗口，需要点击"接收短信验证码"选项

        Returns:
            bool: 是否成功点击了选项

        使用Playwright的getByText定位器，支持React虚拟DOM
        """
        try:
            # 检测页面上是否包含"接收短信验证码"文字
            page_text = await page.inner_text("body")

            # 如果已经有"短信已发送"文字，说明已经点击过了，不再重复点击
            if "短信已发送" in page_text or "请输入验证码" in page_text:
                return False

            if "接收短信验证码" not in page_text:
                return False

            logger.info("🔍 检测到'接收短信验证码'文字，尝试点击...")

            # 方法1: 使用Playwright的文本定位器（最可靠）
            try:
                # 等待包含"接收短信验证码"的元素可见
                locator = page.get_by_text("接收短信验证码", exact=True)
                if await locator.is_visible(timeout=2000):
                    logger.info("🎯 使用 get_by_text 点击")
                    await locator.click(timeout=5000)
                    logger.info("✅ 成功点击'接收短信验证码'")
                    await page.wait_for_timeout(1500)
                    return True
            except Exception as e:
                logger.debug(f"get_by_text 点击失败: {e}")

            # 方法2: 使用文本选择器（备用）
            try:
                await page.click('text="接收短信验证码"', timeout=5000)
                logger.info("✅ 使用文本选择器成功点击")
                await page.wait_for_timeout(1500)
                return True
            except Exception as e:
                logger.debug(f"文本选择器点击失败: {e}")

            # 方法3: 使用CSS+文本组合选择器
            try:
                # 查找包含此文字的div或其他元素
                await page.click('div:has-text("接收短信验证码")', timeout=5000)
                logger.info("✅ 使用组合选择器成功点击")
                await page.wait_for_timeout(1500)
                return True
            except Exception as e:
                logger.debug(f"组合选择器点击失败: {e}")

            logger.warning("⚠️ 所有点击方法都失败了")
            return False

        except Exception as e:
            logger.debug(f"处理身份验证窗口时出错: {e}")
            return False

    async def _handle_save_login_dialog(self, page: Page) -> bool:
        """处理'保存登录信息'对话框

        验证通过后会弹出对话框询问是否保存登录信息
        包含"取消"和"保存"两个按钮

        Returns:
            bool: 是否成功处理了对话框（存在则点击保存，不存在则跳过）
        """
        try:
            # 检测是否存在"保存登录信息"对话框
            # 使用text查找，因为对话框ID不确定
            has_dialog = await page.evaluate("""
                () => {
                    const allElements = Array.from(document.querySelectorAll('*'));
                    return allElements.some(el =>
                        el.textContent?.includes('保存登录信息')
                    );
                }
            """)

            if not has_dialog:
                # 没有对话框，可能已自动跳过或直接登录
                return False

            logger.info("检测到'保存登录信息'对话框，点击'保存'...")

            # 查找并点击"保存"按钮
            result = await page.evaluate("""
                () => {
                    const allElements = Array.from(document.querySelectorAll('*'));
                    // 查找"保存"按钮（同时检查文本和是否可点击）
                    const saveBtn = allElements.find(el =>
                        el.textContent?.trim() === '保存' &&
                        !el.disabled &&
                        (el.tagName === 'DIV' || el.tagName === 'BUTTON')
                    );
                    if (saveBtn) {
                        saveBtn.click();
                        return true;
                    }
                    return false;
                }
            """)

            if result:
                logger.info("✅ 成功点击'保存'按钮")
                await page.wait_for_timeout(1000)
                return True
            else:
                logger.warning("⚠️ 找到'保存登录信息'对话框但无法点击保存按钮")
                return False

        except Exception as e:
            logger.debug(f"处理'保存登录信息'对话框时出错: {e}")
            return False

    async def _verify_login_on_page(self, page) -> bool:
        """Verify login by checking multiple indicators.

        检查方法（按优先级）：
        1. URL是否跳转到 jingxuan 或 user 页面（最准确）
        2. 页面是否有用户头像
        3. sessionid cookie 是否存在且有效
        """
        try:
            # 方法1: 检查URL是否跳转（调研发现登录成功后会跳转）
            current_url = page.url
            if 'jingxuan' in current_url or 'user' in current_url:
                logger.info(f"✅ 登录成功检测: URL已跳转到 {current_url}")
                return True

            # 方法2: 检查页面是否有登录用户特征
            logged_in = await page.evaluate("""
                () => {
                    // 检查是否有用户头像
                    const avatar = document.querySelector('[data-e2e="user-info"] img, .avatar-wrapper img, [class*="avatar"] img');
                    // 检查是否有登录按钮（如果有则说明未登录）
                    const loginBtn = document.querySelector('[class*="login-guide"], [class*="login-panel"]');
                    // 有头像或没有登录按钮都表示已登录
                    return !!(avatar || !loginBtn);
                }
            """)
            if logged_in:
                logger.info("✅ 登录成功检测: 页面显示用户特征")
                return True

            # 方法3: 检查 sessionid cookie
            cookies = await self._context.cookies(settings.DOUYIN_BASE_URL)
            for c in cookies:
                if c["name"] == "sessionid" and c.get("value"):
                    if len(c["value"]) > 10:
                        logger.info(f"✅ 登录成功检测: sessionid有效 (length={len(c['value'])})")
                        return True

            logger.warning("⚠️ 无法确认登录成功")
            return False

        except Exception as e:
            logger.warning(f"Page verification error: {e}")
            # 降级检查：只看cookie
            try:
                cookies = await self._context.cookies(settings.DOUYIN_BASE_URL)
                for c in cookies:
                    if c["name"] == "sessionid" and c.get("value") and len(c["value"]) > 10:
                        return True
            except:
                pass
            return False

    async def screenshot_page(self, page: Page) -> str:
        """截图返回 base64 data URI (JPEG)"""
        buf = await page.screenshot(type="jpeg", quality=60)
        b64 = base64.b64encode(buf).decode()
        return f"data:image/jpeg;base64,{b64}"

    async def detect_verify_code_input(self, page: Page) -> dict | None:
        """检测验证码输入框

        Returns:
            dict | None: 包含手机号 {"phone": "138****1234"} 或 None

        调研发现：
        - 短信已发送后会显示输入框
        - 输入框ID可能是动态的，通过placeholder检测更可靠
        """
        try:
            # 检测页面上是否有"短信已发送"或"请输入验证码"文字
            page_text = await page.inner_text("body")
            if "短信已发送" not in page_text and "请输入验证码" not in page_text:
                return None

            # 全局查找输入框（不限定在验证窗口内）
            has_input = await page.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input'));
                    return inputs.some(inp =>
                        (inp.placeholder?.includes('验证码') || inp.placeholder?.includes('请输入')) &&
                        inp.offsetParent !== null  // 确保可见
                    );
                }
            """)

            if not has_input:
                return None

            # 提取手机号
            import re
            m = re.search(r"1[3-9]\d\*{4}\d{4}", page_text)
            phone = m.group(0) if m else ""

            logger.info(f"✅ 检测到验证码输入框，手机号: {phone}")
            return {"phone": phone}

        except Exception as e:
            logger.debug(f"检测验证码输入框时出错: {e}")
            return None

    async def fill_verify_code(self, page: Page, code: str) -> bool:
        """填入验证码并点击确认按钮

        Args:
            page: Playwright页面对象
            code: 6位验证码

        Returns:
            bool: 是否成功填入并提交

        调研发现：
        - 验证窗口: #uc-second-verify
        - 输入框: #button-input（但有两个！需要使用 #button-input:not(.tnpNAdqe)）
        - 验证按钮: DIV元素，文本为"验证"，class 包含 primary-Npo6wt

        ⚠️ 重要：页面上存在两个 #button-input 元素！
        - 第一个：class="tnpNAdqe _Yqor1vk"，总是空的
        - 第二个：class="input-lrnhMm"，真正可用的
        - 必须使用更精确的选择器：#button-input:not(.tnpNAdqe)
        """
        try:
            # 步骤1: 记录当前页面状态
            current_url = page.url
            logger.info(f"🔍 当前页面 URL: {current_url}")

            # 步骤2: 检查验证窗口是否存在
            verify_window_exists = await page.evaluate("""() => {
                return document.getElementById('uc-second-verify') !== null;
            }""")
            logger.info(f"🔍 验证窗口存在: {verify_window_exists}")

            # 步骤3: 等待输入框出现（使用更精确的选择器避开旧输入框）
            logger.info("⏳ 等待验证码输入框出现...")
            try:
                # ⚠️ 不能直接使用 #button-input，会找到第一个空的！
                # 使用 :not() 排除旧输入框
                inp = await page.wait_for_selector('#button-input:not(.tnpNAdqe)', timeout=5000, state='visible')
                logger.info(f"✅ 找到输入框 #button-input:not(.tnpNAdqe)")
            except Exception as e:
                logger.error(f"❌ 等待输入框超时: {e}")

                # 调试：列出页面上所有输入框
                all_inputs = await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input');
                    return Array.from(inputs).map(inp => ({
                        id: inp.id,
                        name: inp.name,
                        type: inp.type,
                        placeholder: inp.placeholder,
                        visible: inp.offsetParent !== null
                    }));
                }""")
                logger.error(f"🔍 页面上所有输入框: {all_inputs}")
                return False

            # 步骤4: 填入验证码（先清空再填充）
            await inp.fill("")
            await asyncio.sleep(0.1)  # 短暂延迟确保清空生效
            await inp.fill(code)
            logger.info(f"✅ 已填入验证码: {code}")

            # 验证填充成功
            filled_value = await inp.input_value()
            logger.info(f"🔍 输入框当前值: '{filled_value}'")

            # 步骤3: 查找并点击验证按钮（使用精确的选择器）
            result = await page.evaluate("""
                () => {
                    const verifyWindow = document.getElementById('uc-second-verify');
                    if (!verifyWindow) {
                        return { success: false, reason: 'verify_window_not_found' };
                    }

                    // 查找所有包含"验证"文本的 DIV
                    const allDivs = Array.from(verifyWindow.querySelectorAll('div'));
                    const verifyBtn = allDivs.find(el =>
                        el.textContent?.trim() === '验证' &&
                        el.classList.contains('primary-Npo6wt') &&  // 主按钮样式
                        !el.classList.contains('disabled') &&  // 不是禁用状态
                        el.offsetParent !== null  // 按钮可见
                    );

                    if (verifyBtn) {
                        verifyBtn.click();
                        return { success: true, reason: 'clicked' };
                    }

                    return { success: false, reason: 'button_not_found_or_disabled', found_buttons: allDivs.filter(el => el.textContent?.includes('验证')).map(el => el.className) };
                }
            """)

            if result.get('success'):
                logger.info("✅ 成功点击验证按钮")
                return True
            else:
                reason = result.get('reason', 'unknown')
                logger.warning(f"⚠️ 点击验证按钮失败: {reason}")
                if 'found_buttons' in result:
                    logger.debug(f"找到的按钮class: {result['found_buttons']}")
                return False

        except Exception as e:
            logger.error(f"填入验证码时出错: {e}")
            return False

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Engine not started")
        return self._context


# Global singleton
engine = ScraperEngine()
