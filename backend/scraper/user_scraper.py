import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Callable

from playwright.async_api import Page

from backend.config import settings
from backend.scraper.engine import engine
from backend.scraper.interceptor import ResponseInterceptor
from backend.db import crud
from backend.db.models import User, Work

logger = logging.getLogger(__name__)


class UserScraper:
    def __init__(self):
        self.interceptor = ResponseInterceptor()

    async def scrape_profile(self, task_id: int, sec_user_id: str, page: Page | None = None) -> User | None:
        """Get user profile from API or SSR data.

        Args:
            task_id: Task ID for page management
            sec_user_id: User's secure ID
            page: Optional existing page to reuse. If None, creates a new page.
        """
        # 如果传入了页面, 直接使用 API 拦截方式（SSR 数据可能不可用）
        if page:
            return await self._scrape_profile_from_api(task_id, sec_user_id, is_current_user=False, existing_page=page)

        # 优先尝试从 SSR 数据读取（对于当前登录用户）
        current_user_id = await engine.get_current_user_id()
        is_current_user = (current_user_id == sec_user_id)

        if is_current_user:
            logger.info(f"Trying to get current user {sec_user_id} from SSR data")
            user_from_ssr = await self._get_user_from_ssr(task_id, sec_user_id)
            if user_from_ssr:
                # 保存到数据库
                await crud.upsert_user(user_from_ssr)
                logger.info(f"✅ Got user from SSR: {user_from_ssr.nickname} ({sec_user_id})")
                return user_from_ssr
            else:
                logger.info(f"No SSR data for current user, falling back to API")

        # SSR 数据不可用, 使用 API 拦截方式
        return await self._scrape_profile_from_api(task_id, sec_user_id, is_current_user)

    async def _get_user_from_ssr(self, task_id: int, sec_user_id: str) -> User | None:
        """Try to extract user info from SSR_RENDER_DATA."""
        page = None
        try:
            page = await engine.acquire_page(task_id)

            # 导航到用户主页以获取 SSR 数据
            url = f"{settings.DOUYIN_BASE_URL}/user/self"
            logger.info(f"SSR: Navigating to {url} for user {sec_user_id}")
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.warning(f"SSR: Failed to navigate to user page")
                return None

            # 等待页面加载完成
            await page.wait_for_timeout(2000)

            # 从 SSR_RENDER_DATA 读取用户信息
            # ✅ 正确路径: window.SSR_RENDER_DATA.app.user.info
            user_data = await page.evaluate("""
                () => {
                    if (!window.SSR_RENDER_DATA?.app?.user?.info) {
                        return null;
                    }

                    const info = window.SSR_RENDER_DATA.app.user.info;
                    const user = window.SSR_RENDER_DATA.app.user;

                    return {
                        sec_user_id: info.secUid || info.uid,
                        uid: info.uid || info.secUid,
                        nickname: info.nickname || info.realName || user.nickname || info.shortId,
                        avatar_url: info.avatarUrl || info.avatar300Url,
                        douyin_id: info.shortId,
                        signature: info.desc || user.desc || '',
                        following_count: info.followingCount || user.followingCount || 0,
                        follower_count: info.followerCount || user.followerCount || 0,
                        favoriting_count: info.favoritingCount || user.favoritingCount || 0,
                        aweme_count: info.awemeCount || user.awemeCount || 0,
                        total_favorited: info.totalFavorited || user.totalFavorited || 0
                    };
                }
            """)

            if not user_data or not user_data.get('sec_user_id'):
                logger.debug(f"SSR: No user data found for {sec_user_id}")
                return None

            # 补充缺失的字段
            user_data['backend_id'] = sec_user_id

            # 确保必需字段存在
            if not user_data.get('nickname'):
                user_data['nickname'] = f"用户_{sec_user_id[:8]}"

            logger.info(f"✅ SSR: Found user {user_data['nickname']} ({sec_user_id})")

            # 解析用户对象
            user = User(**user_data)
            return user

        except Exception as e:
            logger.debug(f"Failed to get user from SSR: {e}")
            return None
        finally:
            if page:
                try:
                    await engine.release_page(task_id)
                    logger.debug(f"Released page for task #{task_id} in _get_user_from_ssr")
                except Exception as e:
                    logger.warning(f"Failed to release page: {e}")

    async def _scrape_profile_from_api(self, task_id: int, sec_user_id: str, is_current_user: bool, existing_page: Page | None = None) -> User | None:
        """Navigate to user page and intercept profile API response.

        Args:
            task_id: Task ID for page management
            sec_user_id: User's secure ID
            is_current_user: Whether this is the current logged-in user
            existing_page: Optional existing page to reuse. If None, creates a new page.
        """
        own_page = False

        if existing_page:
            # 复用传入的页面
            page = existing_page
            own_page = False
            logger.debug(f"Reusing existing page for profile scrape: {sec_user_id[:20]}...")
        else:
            # 创建新页面
            page = await engine.acquire_page(task_id)
            own_page = True
            logger.debug(f"Acquired new page for profile scrape: {sec_user_id[:20]}...")

        self.interceptor.clear()
        await self.interceptor.setup(page)

        try:
            # 检查是否已经在正确的用户页面
            current_url = page.url
            # 注意：不要在这里调用 get_current_user_id()，因为它会导航到 /user/self
            # is_current_user 参数已经从外部传入

            # 如果已经在目标用户页面，不需要重新导航
            # 注意：需要精确匹配，避免 /user/self?showTab=like 被误判为 /user/self
            if is_current_user:
                # 当前用户：必须在 /user/self 且不能有 showTab 参数
                already_on_page = ("/user/self" in current_url and
                                   "showTab" not in current_url)
            else:
                # 其他用户：必须在 /user/{sec_user_id} 且不能有 showTab 参数
                target_url = f"/user/{sec_user_id}"
                already_on_page = (target_url in current_url and
                                   "showTab" not in current_url)

            if not already_on_page:
                # 需要导航到目标页面
                if is_current_user:
                    logger.info(f"Navigating to /user/self for current user: {sec_user_id}")
                    url = f"{settings.DOUYIN_BASE_URL}/user/self"
                else:
                    logger.info(f"Navigating to /user/{sec_user_id}")
                    url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"

                ok = await engine.safe_goto(page, url)
                if not ok:
                    logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                    return None
            else:
                logger.info(f"Already on user page for {sec_user_id}, skipping navigation")

            # Wait for profile API response
            # 抖音 API 路径已更新：使用 query/user 替代 user/profile/other
            data = await self.interceptor.wait_for("query/user", timeout=10)
            if not data:
                # 尝试旧的 API 路径（向后兼容）
                logger.info("No data from query/user, trying user/profile/other")
                data = await self.interceptor.wait_for("user/profile/other", timeout=5)
            if not data:
                # 尝试 self 端点（当前用户可能使用）
                logger.info("No data from user/profile/other, trying user/profile/self")
                data = await self.interceptor.wait_for("user/profile/self", timeout=5)

            if not data:
                logger.warning(f"No profile data received for {sec_user_id}")
                # 调试：列出所有拦截到的 API
                all_apis = self.interceptor.get_captured_urls()
                logger.warning(f"Captured APIs: {all_apis}")
                return None

            user_info = data.get("user", {})
            if not user_info:
                # 这是正常的回退流程：API 返回的数据可能不完整，后续会尝试其他方式
                logger.info(f"API response missing 'user' field for {sec_user_id[:20]}... (will retry with fallback)")
                return None

            user = self._parse_user(user_info, sec_user_id)
            await crud.upsert_user(user)
            logger.info(f"Scraped profile: {user.nickname} ({sec_user_id[:20]}...)")
            return user

        finally:
            await self.interceptor.teardown()
            # 只有在我们自己创建的页面时才释放
            if own_page:
                try:
                    await engine.release_page(task_id)
                    logger.debug(f"Released page for task #{task_id}")
                except Exception as e:
                    logger.warning(f"Failed to release page for task #{task_id}: {e}")

    async def scrape_works(
        self, task_id: int, sec_user_id: str, max_pages: int | None = None, max_count: int | None = None,
        on_page: Callable | None = None,
    ) -> list[Work]:
        """Scrape user's works list with pagination.

        Args:
            task_id: Unique task identifier for page management
            sec_user_id: User ID to scrape
            max_pages: Maximum number of pages to scrape (deprecated, use max_count)
            max_count: Maximum number of works to scrape
            on_page: Callback function(page_num, total_pages) for progress tracking
        """
        logger.info(f"Starting scrape_works for {sec_user_id}, max_pages={max_pages}, max_count={max_count}")
        page = await engine.acquire_page(task_id)
        self.interceptor.clear()
        await self.interceptor.setup(page)
        logger.info(f"Interceptor setup complete for {sec_user_id}")

        all_works = []
        page_count = 0

        try:
            # Navigate to user page if not already there
            current_url = page.url
            user_url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            # 检查是否已经在目标用户的主页（不能是 showTab=like 等子页面）
            if sec_user_id not in current_url or "showTab" in current_url:
                logger.info(f"Navigating to {user_url}")
                ok = await engine.safe_goto(page, user_url)
                if not ok:
                    logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                    return []
                logger.info(f"Navigation successful, current URL: {page.url}")
            else:
                logger.info(f"Already on user page: {page.url}")

            # Wait for initial works data
            logger.info(f"Waiting for aweme/post API (timeout=15s)...")
            data = await self.interceptor.wait_for("aweme/post", timeout=15)
            if data:
                logger.info(f"Got initial data, has_more={data.get('has_more', 0)}")
                works = self._parse_works_response(data, sec_user_id)
                all_works.extend(works)
                page_count += 1
                logger.info(f"Page {page_count}: got {len(works)} works")
            else:
                logger.warning(f"No data received from aweme/post API!")
                # Log captured URLs for debugging
                captured = self.interceptor.get_captured_urls()
                logger.warning(f"Captured URLs: {captured[:5]}")  # First 5 URLs

            # Pagination loop
            effective_max = max_pages or 999
            has_more = data.get("has_more", 0) if data else 0
            if on_page:
                on_page(page_count, effective_max)
            while has_more:
                # Check max_count limit
                if max_count and len(all_works) >= max_count:
                    logger.info(f"Reached max_count limit: {len(all_works)} >= {max_count}")
                    break

                if max_pages and page_count >= max_pages:
                    break

                # Random delay to avoid detection
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Longer pause every 3-5 pages to mimic human behavior
                if page_count > 0 and page_count % random.randint(3, 5) == 0:
                    long_pause = random.uniform(5, 10)
                    logger.debug(f"Anti-detection long pause: {long_pause:.1f}s")
                    await asyncio.sleep(long_pause)

                # Check for captcha before scrolling
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        break

                # Scroll the route-scroll-container to trigger next page load
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                """)
                await page.wait_for_timeout(1000)

                data = await self.interceptor.wait_for("aweme/post", timeout=10)
                if not data:
                    break

                works = self._parse_works_response(data, sec_user_id)
                if not works:
                    break

                all_works.extend(works)
                page_count += 1
                has_more = data.get("has_more", 0)
                logger.info(f"Page {page_count}: got {len(works)} works (total: {len(all_works)})")
                if on_page:
                    on_page(page_count, effective_max)

            # Trim to max_count if specified
            if max_count and len(all_works) > max_count:
                logger.info(f"Trimming works from {len(all_works)} to {max_count}")
                all_works = all_works[:max_count]

            logger.info(f"Scraped {len(all_works)} works for {sec_user_id[:20]}...")
            return all_works

        finally:
            await self.interceptor.teardown()
            # Release the page back to the pool for this task
            try:
                await engine.release_page(task_id)
                logger.debug(f"Released page for task #{task_id}")
            except Exception as e:
                logger.warning(f"Failed to release page for task #{task_id}: {e}")

    async def scrape_likes(
        self, task_id: int, sec_user_id: str, max_pages: int | None = None, max_count: int | None = None,
        on_page: Callable | None = None, check_cancelled: Callable | None = None,
    ) -> list[Work]:
        """Scrape current user's liked videos (喜欢) with pagination."""
        page = await engine.acquire_page(task_id)
        self.interceptor.clear()
        await self.interceptor.setup(page)

        all_works = []
        page_count = 0

        try:
            # Navigate to likes page
            url = f"{settings.DOUYIN_BASE_URL}/user/self?showTab=like"
            logger.info(f"Navigating to likes page: {url}")
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error("Failed to load likes page (navigation failed or captcha timeout)")
                return []

            logger.info("Page loaded, waiting for aweme/favorite API (timeout=15s)...")

            # Wait for initial likes data (aweme/favorite API)
            data = await self.interceptor.wait_for("aweme/favorite", timeout=15)

            if not data:
                logger.warning("No aweme/favorite API received, checking captured APIs...")
                all_apis = self.interceptor.get_captured_urls()
                logger.warning(f"Captured APIs: {all_apis}")

            if data:
                aweme_list = data.get("aweme_list", [])
                works = self._parse_works_from_list(aweme_list, sec_user_id)
                all_works.extend(works)
                page_count += 1
                logger.info(f"Likes Page {page_count}: got {len(works)} works")

            # Pagination loop
            effective_max = max_pages or 999
            # Check if there's more data
            # Strategy: continue if we got data, stop if API returns empty or fails
            first_page_size = len(data.get("aweme_list", [])) if data else 0
            has_more = first_page_size > 0
            if on_page:
                on_page(page_count, effective_max)

            while has_more and page_count < effective_max:
                # Check if task is cancelled
                if check_cancelled and await check_cancelled():
                    logger.info(f"Task #{task_id} was cancelled, stopping pagination")
                    break

                # Check max_count limit before continuing
                if max_count and len(all_works) >= max_count:
                    logger.info(f"Reached max_count limit: {len(all_works)} >= {max_count}")
                    break

                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        logger.warning("Captcha detected and not resolved, stopping pagination")
                        break

                # Improved scrolling strategy: scroll the route-scroll-container to trigger lazy loading
                logger.info("Scrolling to load more content...")

                # Find and scroll the correct scrollable container
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            // Method 1: Scroll to near bottom
                            container.scrollTop = container.scrollHeight - 800;
                        }
                    }
                """)
                await page.wait_for_timeout(2000)

                # Method 2: Scroll to absolute bottom
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                """)
                await page.wait_for_timeout(2000)

                # Method 3: Small incremental scroll
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop += 300;
                        }
                    }
                """)
                await page.wait_for_timeout(1000)

                # Method 4: Scroll back to bottom
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                """)
                await page.wait_for_timeout(3000)  # Longer wait for API to respond

                data = await self.interceptor.wait_for("aweme/favorite", timeout=30)  # Increased timeout for slower loading
                if not data:
                    logger.warning("No more data received from API, stopping pagination")
                    break

                aweme_list = data.get("aweme_list", [])
                works = self._parse_works_from_list(aweme_list, sec_user_id)

                # Stop conditions:
                # 1. Empty array returned → no more data
                # 2. Significantly fewer items than first page → likely last page
                if not works:
                    logger.info("Received empty work list, reached end of likes")
                    break

                # Optional: Check if we got substantially fewer items (might indicate last page)
                if len(aweme_list) < first_page_size * 0.5:
                    logger.info(f"Got significantly fewer items ({len(aweme_list)} vs {first_page_size}), likely last page")
                    # Still process this page, but don't continue after

                all_works.extend(works)
                page_count += 1

                # Decide whether to continue based on data received
                # Continue only if we got a reasonable amount of data
                has_more = len(aweme_list) >= first_page_size * 0.5

                logger.info(f"Likes Page {page_count}: got {len(works)} works (total: {len(all_works)})")
                if on_page:
                    on_page(page_count, effective_max)

            # Trim to max_count if specified
            if max_count and len(all_works) > max_count:
                logger.info(f"Trimming works from {len(all_works)} to {max_count}")
                all_works = all_works[:max_count]

            logger.info(f"Scraped {len(all_works)} liked videos")
            return all_works

        finally:
            await self.interceptor.teardown()
            # Release the page back to the pool for this task
            try:
                await engine.release_page(task_id)
                logger.debug(f"Released page for task #{task_id}")
            except Exception as e:
                logger.warning(f"Failed to release page for task #{task_id}: {e}")

    async def scrape_favorites(
        self, task_id: int, sec_user_id: str, max_pages: int | None = None, max_count: int | None = None,
        on_page: Callable | None = None, check_cancelled: Callable | None = None,
    ) -> list[Work]:
        """Scrape current user's favorite videos (收藏) with pagination."""
        page = await engine.acquire_page(task_id)
        self.interceptor.clear()
        await self.interceptor.setup(page)

        all_works = []
        page_count = 0

        try:
            # Navigate to favorites page
            url = f"{settings.DOUYIN_BASE_URL}/user/self?showTab=favorite_collection"
            logger.info(f"Navigating to favorites page: {url}")
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error("Failed to load favorites page (navigation failed or captcha timeout)")
                return []

            logger.info("Page loaded, waiting for aweme/favorite API (timeout=15s)...")

            # Wait for initial favorites data
            data = await self.interceptor.wait_for("aweme/favorite", timeout=15)

            if not data:
                logger.warning("No aweme/favorite API received, checking captured APIs...")
                all_apis = self.interceptor.get_captured_urls()
                logger.warning(f"Captured APIs: {all_apis}")

            if data:
                aweme_list = data.get("aweme_list", [])
                works = self._parse_works_from_list(aweme_list, sec_user_id)
                all_works.extend(works)
                page_count += 1
                logger.info(f"Favorites Page {page_count}: got {len(works)} works")

            # Pagination loop
            effective_max = max_pages or 999
            # Check if there's more data
            first_page_size = len(data.get("aweme_list", [])) if data else 0
            has_more = first_page_size > 0
            if on_page:
                on_page(page_count, effective_max)

            while has_more and page_count < effective_max:
                # Check if task is cancelled
                if check_cancelled and await check_cancelled():
                    logger.info(f"Task #{task_id} was cancelled, stopping pagination")
                    break

                # Check max_count limit before continuing
                if max_count and len(all_works) >= max_count:
                    logger.info(f"Reached max_count limit: {len(all_works)} >= {max_count}")
                    break

                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        logger.warning("Captcha detected and not resolved, stopping pagination")
                        break

                # Improved scrolling strategy: scroll the route-scroll-container to trigger lazy loading
                logger.info("Scrolling to load more content...")

                # Find and scroll the correct scrollable container
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            // Method 1: Scroll to near bottom
                            container.scrollTop = container.scrollHeight - 800;
                        }
                    }
                """)
                await page.wait_for_timeout(2000)

                # Method 2: Scroll to absolute bottom
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                """)
                await page.wait_for_timeout(2000)

                # Method 3: Small incremental scroll
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop += 300;
                        }
                    }
                """)
                await page.wait_for_timeout(1000)

                # Method 4: Scroll back to bottom
                await page.evaluate("""
                    () => {
                        const container = document.querySelector('.route-scroll-container');
                        if (container) {
                            container.scrollTop = container.scrollHeight;
                        }
                    }
                """)
                await page.wait_for_timeout(3000)  # Longer wait for API to respond

                data = await self.interceptor.wait_for("aweme/favorite", timeout=30)  # Increased timeout for slower loading
                if not data:
                    logger.warning("No more data received from API, stopping pagination")
                    break

                aweme_list = data.get("aweme_list", [])
                works = self._parse_works_from_list(aweme_list, sec_user_id)

                # Stop conditions:
                # 1. Empty array returned → no more data
                # 2. Significantly fewer items than first page → likely last page
                if not works:
                    logger.info("Received empty work list, reached end of favorites")
                    break

                # Optional: Check if we got substantially fewer items (might indicate last page)
                if len(aweme_list) < first_page_size * 0.5:
                    logger.info(f"Got significantly fewer items ({len(aweme_list)} vs {first_page_size}), likely last page")
                    # Still process this page, but don't continue after

                all_works.extend(works)
                page_count += 1

                # Decide whether to continue based on data received
                # Continue only if we got a reasonable amount of data
                has_more = len(aweme_list) >= first_page_size * 0.5

                logger.info(f"Favorites Page {page_count}: got {len(works)} works (total: {len(all_works)})")
                if on_page:
                    on_page(page_count, effective_max)

            # Trim to max_count if specified
            if max_count and len(all_works) > max_count:
                logger.info(f"Trimming works from {len(all_works)} to {max_count}")
                all_works = all_works[:max_count]

            logger.info(f"Scraped {len(all_works)} favorite videos")
            return all_works

        finally:
            await self.interceptor.teardown()
            # Release the page back to the pool for this task
            try:
                await engine.release_page(task_id)
                logger.debug(f"Released page for task #{task_id}")
            except Exception as e:
                logger.warning(f"Failed to release page for task #{task_id}: {e}")

    async def scrape_following(
        self, task_id: int, sec_user_id: str, max_count: int | None = None,
        on_page: Callable | None = None,
        existing_page: Page | None = None,
    ) -> list[dict]:
        """Scrape user's following list with pagination using API interception.

        Args:
            task_id: Task ID for page management
            sec_user_id: User's secure ID
            max_count: Maximum number of users to scrape
            on_page: Callback for progress updates
            existing_page: Optional existing page to reuse. If None, creates a new page.

        Returns list of user info dicts with keys:
        - sec_user_id
        - nickname
        - avatar_url
        - douyin_id
        """
        own_page = False

        if existing_page:
            page = existing_page
            logger.debug(f"Reusing existing page for following scrape: {sec_user_id[:20]}...")
        else:
            page = await engine.acquire_page(task_id)
            own_page = True
            logger.debug(f"Acquired new page for following scrape: {sec_user_id[:20]}...")

        self.interceptor.clear()
        await self.interceptor.setup(page)

        # 备用：使用 response 事件监听器捕获 API 响应
        # 存储 response 对象而非立即解析（因为 response.json() 是异步的）
        captured_responses_raw = []

        def on_response(response):
            try:
                if "following/list" in response.url:
                    logger.info(f"[Backup Listener] Captured following/list API: {response.url[:100]}")
                    if response.ok:
                        # 存储 response 对象，稍后异步解析
                        captured_responses_raw.append(response)
            except Exception as e:
                logger.debug(f"Response listener error: {e}")

        page.on("response", on_response)

        async def parse_captured_responses() -> list[dict]:
            """异步解析备用监听器捕获的响应。"""
            results = []
            for resp in captured_responses_raw:
                try:
                    json_data = await resp.json()
                    results.append(json_data)
                except Exception as e:
                    logger.debug(f"Failed to parse backup response: {e}")
            return results

        all_users = []
        page_count = 0
        seen_user_ids = set()  # Track seen users to avoid duplicates

        try:
            # Navigate to user's following page
            url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                return []

            # Click on the "关注" element to open following list modal
            logger.info(f"Clicking following tab for {sec_user_id}")

            # Wait for page to fully load - multiple conditions for reliability
            # 1. Wait for the "关注" text to appear
            await page.wait_for_selector('text=关注', timeout=10000)

            # 2. Additional wait for dynamic content to render
            await asyncio.sleep(1.0)

            # 3. Verify the element is actually clickable (visible and not covered)
            await page.wait_for_function("""
                () => {
                    const statsContainer = document.querySelector('.Q1A_pjwq');
                    if (statsContainer) {
                        const rect = statsContainer.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }
                    // Fallback: check for p element with pattern
                    const allPs = document.querySelectorAll('p');
                    for (const p of allPs) {
                        if (/^关注\\s*\\d+$/.test(p.textContent.trim())) {
                            const rect = p.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }
                    }
                    return false;
                }
            """, timeout=5000)

            # Start waiting for API FIRST (in background), then click
            # This ensures we don't miss the API call that happens immediately after clicking
            logger.info("Waiting for following list API...")
            api_wait_task = asyncio.create_task(
                self.interceptor.wait_for("user/following/list", timeout=15)
            )

            # Small buffer to let interceptor start
            await asyncio.sleep(0.2)

            # Now click the "关注" button
            # VERIFIED in chrome-devtools: Multiple strategies to find and click the element
            clicked = await page.evaluate("""
                () => {
                    // Strategy 1: Find the stats container with class Q1A_pjwq (most reliable)
                    const statsContainer = document.querySelector('.Q1A_pjwq');
                    if (statsContainer) {
                        statsContainer.click();
                        return { clicked: true, method: 'container click' };
                    }

                    // Strategy 2: Find the <p> element containing "关注" followed by digits
                    const allPs = document.querySelectorAll('p');
                    for (const p of allPs) {
                        const text = p.textContent.trim();
                        // Match "关注43", "关注 43", etc. (关注 + optional whitespace + digits)
                        if (/^关注\\s*\\d+$/.test(text)) {
                            p.click();
                            return { clicked: true, method: 'p element click', text: text };
                        }
                    }

                    return { clicked: false, reason: 'No matching element found' };
                }
            """)

            if not clicked:
                logger.warning("Failed to click following button")
                api_wait_task.cancel()
                return []

            logger.info("Clicked successfully, waiting for API response...")

            # Wait for the API call (already started in background)
            try:
                data = await api_wait_task
            except asyncio.TimeoutError:
                logger.warning("Interceptor timeout, checking backup listener...")
                data = None

            # 如果主拦截器没有数据，尝试备用监听器
            if not data:
                backup_data = await parse_captured_responses()
                if backup_data:
                    logger.info(f"Got {len(backup_data)} responses from backup listener")
                    data = backup_data[0]  # 使用第一个响应
                else:
                    logger.error("No data from following list API (both interceptor and backup)")
                    return []

            effective_max = max_count or 9999

            # Parse the API response
            def parse_api_response(response_data: dict) -> list[dict]:
                """Parse user data from API response.

                API response structure:
                {
                    "followings": [...],  # 用户列表 (实际 API 返回的结构)
                    "extra": {...}
                }

                每个用户对象包含:
                - sec_uid: 用户安全 ID
                - nickname: 昵称
                - avatar_larger/avatar_thumb: 头像信息
                - unique_id/short_id: 抖音号
                """
                users = []
                try:
                    if not isinstance(response_data, dict):
                        return users

                    # 实际 API 返回的是 "followings" 字段，不是 "data.user_infos"
                    followings = response_data.get("followings", [])
                    if not followings:
                        # 兼容旧结构
                        followings = response_data.get("data", {}).get("user_infos", [])

                    for user_info in followings:
                        if not isinstance(user_info, dict):
                            continue

                        # 实际 API 使用 "sec_uid"，兼容 "sec_user_id"
                        sec_uid = user_info.get("sec_uid") or user_info.get("sec_user_id", "")
                        if not sec_uid or sec_uid in seen_user_ids:
                            continue

                        seen_user_ids.add(sec_uid)

                        # Extract user information
                        user_data = {
                            "sec_user_id": sec_uid,
                            "nickname": user_info.get("nickname", ""),
                            "avatar_url": "",
                            "douyin_id": ""
                        }

                        # Get avatar URL
                        avatar_larger = user_info.get("avatar_larger", {})
                        if isinstance(avatar_larger, dict):
                            url_list = avatar_larger.get("url_list", [])
                            if url_list:
                                user_data["avatar_url"] = url_list[0]
                        else:
                            avatar_thumb = user_info.get("avatar_thumb", {})
                            if isinstance(avatar_thumb, dict):
                                url_list = avatar_thumb.get("url_list", [])
                                if url_list:
                                    user_data["avatar_url"] = url_list[0]

                        # Get douyin_id
                        user_data["douyin_id"] = user_info.get("unique_id", "") or user_info.get("short_id", "")

                        users.append(user_data)
                        logger.debug(f"Parsed user: {user_data['nickname']} ({user_data['douyin_id']})")
                except Exception as e:
                    logger.warning(f"Error parsing API response: {e}")
                return users

            # Parse initial response
            users = parse_api_response(data)
            if users:
                all_users.extend(users)
                page_count += 1
                logger.info(f"Following Page {page_count}: got {len(users)} users")

                if on_page:
                    on_page(page_count, effective_max)

            # Pagination loop - scroll to trigger more API calls
            while len(all_users) < effective_max:
                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        break

                # Scroll to trigger next page API call
                # 尝试多种滚动容器选择器
                scrolled = await page.evaluate("""
                    () => {
                        // 尝试多种可能的滚动容器
                        const selectors = [
                            '[role="tabpanel"]',
                            '[class*="modal"]',
                            '[class*="dialog"]',
                            '[class*="scroll"]',
                            '.following-list',
                            '[data-e2e="user-following-list"]'
                        ];

                        for (const selector of selectors) {
                            const container = document.querySelector(selector);
                            if (container && container.scrollHeight > container.clientHeight) {
                                // 渐进式滚动
                                const currentScroll = container.scrollTop;
                                container.scrollTop = container.scrollHeight;

                                // 检查是否真的滚动了
                                if (container.scrollTop !== currentScroll) {
                                    console.log('Scrolled container:', selector);
                                    return true;
                                }
                            }
                        }

                        // 如果没有找到特定容器，尝试滚动整个弹窗内容
                        const allScrollable = Array.from(document.querySelectorAll('*')).filter(el => {
                            return el.scrollHeight > el.clientHeight &&
                                   el.clientHeight > 100 &&
                                   el.clientHeight < 800;
                        });

                        if (allScrollable.length > 0) {
                            // 滚动最大的那个
                            const largest = allScrollable.reduce((a, b) =>
                                a.scrollHeight > b.scrollHeight ? a : b
                            );
                            largest.scrollTop = largest.scrollHeight;
                            return true;
                        }

                        return false;
                    }
                """)

                if not scrolled:
                    logger.warning("Could not find scrollable container in following modal")
                    # 尝试发送键盘 PageDown 事件
                    await page.keyboard.press('PageDown')
                    await asyncio.sleep(0.5)

                # 等待滚动生效
                await asyncio.sleep(2)

                # Wait for next API call (增加超时时间)
                logger.info("Waiting for next following list API...")
                next_data = await self.interceptor.wait_for("user/following/list", timeout=15)

                if not next_data:
                    logger.info("No more data from API, stopping pagination")
                    break

                # Parse response
                users = parse_api_response(next_data)
                if not users:
                    logger.info("No new users in response, stopping pagination")
                    break

                all_users.extend(users)
                page_count += 1
                logger.info(f"Following Page {page_count}: got {len(users)} users (total: {len(all_users)})")

                if on_page:
                    on_page(page_count, effective_max)

            # Trim to max_count
            if max_count and len(all_users) > max_count:
                all_users = all_users[:max_count]

            logger.info(f"Scraped {len(all_users)} following users for {sec_user_id[:20]}...")
            return all_users

        finally:
            await self.interceptor.teardown()
            # 清理事件监听器
            try:
                page.remove_listener("response", on_response)
                logger.debug("Removed backup response listener")
            except Exception as e:
                logger.debug(f"Failed to remove response listener: {e}")
            # 只有在我们自己创建的页面时才释放
            if own_page:
                try:
                    await engine.release_page(task_id)
                    logger.debug(f"Released page for task #{task_id}")
                except Exception as e:
                    logger.warning(f"Failed to release page for task #{task_id}: {e}")

    def _parse_user(self, user_info: dict, sec_user_id: str) -> User:
        """Parse user info from API response."""
        return User(
            sec_user_id=sec_user_id,
            uid=str(user_info.get("uid", "")),
            nickname=user_info.get("nickname", ""),
            avatar_url=user_info.get("avatar_larger", {}).get("url_list", [""])[0]
                if isinstance(user_info.get("avatar_larger"), dict)
                else user_info.get("avatar_thumb", {}).get("url_list", [""])[0]
                if isinstance(user_info.get("avatar_thumb"), dict)
                else "",
            signature=user_info.get("signature", ""),
            douyin_id=user_info.get("unique_id", "") or user_info.get("short_id", ""),
            location=user_info.get("ip_location", "")
                or user_info.get("city", ""),
            follower_count=user_info.get("follower_count", 0),
            following_count=user_info.get("following_count", 0),
            total_favorited=user_info.get("total_favorited", 0),
            aweme_count=user_info.get("aweme_count", 0),
            is_verified=bool(user_info.get("custom_verify")),
            verification_type=user_info.get("custom_verify", ""),
            extra_data=json.dumps(
                {k: user_info[k] for k in ("enterprise_verify_reason", "commerce_info")
                 if k in user_info},
                ensure_ascii=False,
            ) or None,
        )

    def _parse_works_response(self, data: dict, sec_user_id: str) -> list[Work]:
        """Parse works list from API response."""
        aweme_list = data.get("aweme_list", [])
        works = []

        for item in aweme_list:
            try:
                work = self._parse_single_work(item, sec_user_id)
                works.append(work)
            except Exception as e:
                logger.warning(f"Failed to parse work: {e}")
                continue

        return works

    def _parse_works_from_list(self, aweme_list: list, sec_user_id: str) -> list[Work]:
        """Parse works from aweme_list directly."""
        works = []

        for item in aweme_list:
            try:
                work = self._parse_single_work(item, sec_user_id)
                works.append(work)
            except Exception as e:
                logger.warning(f"Failed to parse work: {e}")
                continue

        return works

    def _parse_single_work(self, item: dict, expected_sec_user_id: str) -> Work:
        """Parse a single work item from API response.
        
        Args:
            item: Work data from API
            expected_sec_user_id: The expected user ID (for validation)
        """
        aweme_id = str(item.get("aweme_id", ""))

        # Get the actual author's uid and sec_user_id from the work data
        # This ensures we're using the correct author ID, not the current logged-in user's ID
        author_info = item.get("author", {})
        author_uid = str(author_info.get("uid", ""))  # Real unique identifier (most important)
        actual_sec_user_id = author_info.get("sec_uid") or author_info.get("uid") or expected_sec_user_id
        
        # Log warning if there's a mismatch (for debugging)
        if actual_sec_user_id != expected_sec_user_id:
            logger.warning(f"Author mismatch for work {aweme_id}: expected {expected_sec_user_id[:20]}..., got {actual_sec_user_id[:20]}...")

        aweme_type = item.get("aweme_type", 0)
        is_note = aweme_type in (68, 150) or item.get("images") is not None
        work_type = "note" if is_note else "video"

        desc = item.get("desc", "")

        cover = item.get("video", {}).get("cover", {})
        cover_url = cover.get("url_list", [""])[0] if isinstance(cover, dict) else ""

        duration = item.get("video", {}).get("duration", 0) if not is_note else 0

        stats = item.get("statistics", {})

        text_extra = item.get("text_extra", [])
        hashtags = [t.get("hashtag_name", "") for t in text_extra if t.get("hashtag_name")]

        music = item.get("music", {})
        music_title = music.get("title", "") if isinstance(music, dict) else ""

        create_time = item.get("create_time", 0)
        publish_time = datetime.fromtimestamp(create_time) if create_time else None

        return Work(
            aweme_id=aweme_id,
            uid=author_uid,  # Use the author's real uid (most stable identifier)
            sec_user_id=actual_sec_user_id,  # Use the actual author's current sec_user_id
            type=work_type,
            title=desc,
            cover_url=cover_url,
            duration=duration,
            digg_count=stats.get("digg_count", 0),
            comment_count=stats.get("comment_count", 0),
            share_count=stats.get("share_count", 0),
            collect_count=stats.get("collect_count", 0),
            play_count=stats.get("play_count", 0),
            hashtags=json.dumps(hashtags, ensure_ascii=False) if hashtags else None,
            music_title=music_title,
            publish_time=publish_time,
            extra_data=json.dumps(
                {
                    "video_url": item.get("video", {}).get("play_addr", {}).get("url_list", []),
                    "images": [
                        img.get("url_list", [""])[0]
                        for img in (item.get("images") or [])
                        if isinstance(img, dict)
                    ],
                    "author_uid": author_uid,  # Store the author's real uid for reliable linking
                },
                ensure_ascii=False,
            ),
        )
