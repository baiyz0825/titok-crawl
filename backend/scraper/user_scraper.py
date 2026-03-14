import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Callable

from backend.config import settings
from backend.scraper.engine import engine
from backend.scraper.interceptor import ResponseInterceptor
from backend.db import crud
from backend.db.models import User, Work

logger = logging.getLogger(__name__)


class UserScraper:
    def __init__(self):
        self.interceptor = ResponseInterceptor()

    async def scrape_profile(self, task_id: int, sec_user_id: str) -> User | None:
        """Get user profile from API or SSR data."""
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

        # SSR 数据不可用，使用 API 拦截方式
        return await self._scrape_profile_from_api(task_id, sec_user_id, is_current_user)

    async def _get_user_from_ssr(self, task_id: int, sec_user_id: str) -> User | None:
        """Try to extract user info from SSR_RENDER_DATA."""
        page = None
        try:
            page = await engine.acquire_page(task_id)

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

    async def _scrape_profile_from_api(self, task_id: int, sec_user_id: str, is_current_user: bool) -> User | None:
        """Navigate to user page and intercept profile API response."""
        page = await engine.acquire_page(task_id)
        self.interceptor.clear()
        await self.interceptor.setup(page)

        try:
            # 检查是否已经在正确的用户页面
            current_url = page.url
            current_user_id = await engine.get_current_user_id()
            is_current_user = (current_user_id == sec_user_id)

            # 如果已经在目标用户页面，不需要重新导航
            target_in_url = f"/user/{sec_user_id}" if not is_current_user else "/user/self"
            already_on_page = (
                (is_current_user and "/user/self" in current_url) or
                (not is_current_user and f"/user/{sec_user_id}" in current_url)
            )

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
            # 优先尝试 user/profile/other（更常见），然后是 user/profile/self
            data = await self.interceptor.wait_for("user/profile/other", timeout=10)
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
                logger.warning(f"Empty user info for {sec_user_id}")
                return None

            user = self._parse_user(user_info, sec_user_id)
            await crud.upsert_user(user)
            logger.info(f"Scraped profile: {user.nickname} ({sec_user_id[:20]}...)")
            return user

        finally:
            await self.interceptor.teardown()
            # Release the page back to the pool for this task
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
            if sec_user_id not in current_url:
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

                # Scroll to bottom to trigger next page load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
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
        self, task_id: int, sec_user_id: str, max_pages: int | None = None,
        on_page: Callable | None = None,
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
                logger.error("Failed to load likes page (captcha timeout)")
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
                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        logger.warning("Captcha detected and not resolved, stopping pagination")
                        break

                # Improved scrolling strategy: scroll gradually to trigger lazy loading
                logger.info("Scrolling to load more content...")

                # Method 1: Scroll to near bottom (not absolute bottom to avoid premature stop)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
                await page.wait_for_timeout(2000)

                # Method 2: Scroll to absolute bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                # Method 3: Small incremental scroll to trigger lazy loading
                await page.evaluate("window.scrollBy(0, 300)")
                await page.wait_for_timeout(1000)

                # Method 4: Scroll back to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
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
        self, task_id: int, sec_user_id: str, max_pages: int | None = None,
        on_page: Callable | None = None,
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
                logger.error("Failed to load favorites page (captcha timeout)")
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
                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        logger.warning("Captcha detected and not resolved, stopping pagination")
                        break

                # Improved scrolling strategy: scroll gradually to trigger lazy loading
                logger.info("Scrolling to load more content...")

                # Method 1: Scroll to near bottom (not absolute bottom to avoid premature stop)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
                await page.wait_for_timeout(2000)

                # Method 2: Scroll to absolute bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                # Method 3: Small incremental scroll to trigger lazy loading
                await page.evaluate("window.scrollBy(0, 300)")
                await page.wait_for_timeout(1000)

                # Method 4: Scroll back to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
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
    ) -> list[dict]:
        """Scrape user's following list with pagination.

        Returns list of user info dicts with keys:
        - sec_user_id
        - nickname
        - avatar_url
        - douyin_id
        """
        page = await engine.acquire_page(task_id)
        self.interceptor.clear()
        await self.interceptor.setup(page)

        all_users = []
        page_count = 0

        try:
            # Navigate to user's following page
            url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                return []

            # Click on following tab
            logger.info(f"Navigating to following tab for {sec_user_id}")
            try:
                # Try to click the following tab
                await page.evaluate(f"window.location.href = '{url}?showTab=following'")
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to navigate to following tab: {e}")

            # Wait for following data
            logger.info(f"Waiting for following list API...")
            data = await self.interceptor.wait_for("following/list", timeout=15)
            if not data:
                # Try alternative API endpoint
                logger.warning("No data from following/list, trying user/following")
                data = await self.interceptor.wait_for("user/following", timeout=5)

            if data:
                user_list = data.get("user_list", [])
                for user_info in user_list:
                    user_dict = {
                        "sec_user_id": user_info.get("sec_uid") or user_info.get("secUserId"),
                        "nickname": user_info.get("nickname") or user_info.get("nickName"),
                        "avatar_url": user_info.get("avatar_thumb", {}).get("url_list", [""])[0]
                            if isinstance(user_info.get("avatar_thumb"), dict)
                            else user_info.get("avatarUrl") or "",
                        "douyin_id": user_info.get("unique_id") or user_info.get("shortId") or "",
                    }
                    if user_dict["sec_user_id"]:
                        all_users.append(user_dict)

                page_count += 1
                logger.info(f"Following Page {page_count}: got {len(user_list)} users")

            # Pagination loop
            effective_max = max_count or 9999
            has_more = data.get("has_more", 0) if data else 0
            if on_page:
                on_page(page_count, effective_max)

            while has_more and len(all_users) < effective_max:
                # Random delay
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        break

                # Scroll to trigger next page
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

                data = await self.interceptor.wait_for("following/list", timeout=10)
                if not data:
                    data = await self.interceptor.wait_for("user/following", timeout=5)
                if not data:
                    break

                user_list = data.get("user_list", [])
                for user_info in user_list:
                    user_dict = {
                        "sec_user_id": user_info.get("sec_uid") or user_info.get("secUserId"),
                        "nickname": user_info.get("nickname") or user_info.get("nickName"),
                        "avatar_url": user_info.get("avatar_thumb", {}).get("url_list", [""])[0]
                            if isinstance(user_info.get("avatar_thumb"), dict)
                            else user_info.get("avatarUrl") or "",
                        "douyin_id": user_info.get("unique_id") or user_info.get("shortId") or "",
                    }
                    if user_dict["sec_user_id"]:
                        all_users.append(user_dict)

                page_count += 1
                has_more = data.get("has_more", 0)
                logger.info(f"Following Page {page_count}: got {len(user_list)} users (total: {len(all_users)})")
                if on_page:
                    on_page(page_count, effective_max)

            # Trim to max_count
            if max_count and len(all_users) > max_count:
                all_users = all_users[:max_count]

            logger.info(f"Scraped {len(all_users)} following users for {sec_user_id[:20]}...")
            return all_users

        finally:
            await self.interceptor.teardown()
            # Release the page back to the pool for this task
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

    def _parse_single_work(self, item: dict, sec_user_id: str) -> Work:
        """Parse a single work item from API response."""
        aweme_id = str(item.get("aweme_id", ""))

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
            sec_user_id=sec_user_id,
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
                },
                ensure_ascii=False,
            ),
        )
