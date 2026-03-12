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

    async def scrape_profile(self, sec_user_id: str) -> User | None:
        """Navigate to user page and intercept profile API response."""
        page = await engine.get_page()
        self.interceptor.clear()
        await self.interceptor.setup(page)

        try:
            url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                return None

            # Wait for profile API response
            data = await self.interceptor.wait_for("user/profile/other", timeout=15)
            if not data:
                logger.warning(f"No profile data received for {sec_user_id}")
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

    async def scrape_works(
        self, sec_user_id: str, max_pages: int | None = None,
        on_page: Callable | None = None,
    ) -> list[Work]:
        """Scrape user's works list with pagination."""
        page = await engine.get_page()
        self.interceptor.clear()
        await self.interceptor.setup(page)

        all_works = []
        page_count = 0

        try:
            # Navigate to user page if not already there
            current_url = page.url
            user_url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            if sec_user_id not in current_url:
                ok = await engine.safe_goto(page, user_url)
                if not ok:
                    logger.error(f"Failed to load user page (captcha timeout): {sec_user_id}")
                    return []

            # Wait for initial works data
            data = await self.interceptor.wait_for("aweme/post", timeout=15)
            if data:
                works = self._parse_works_response(data, sec_user_id)
                all_works.extend(works)
                page_count += 1
                logger.info(f"Page {page_count}: got {len(works)} works")

            # Pagination loop
            effective_max = max_pages or 999
            has_more = data.get("has_more", 0) if data else 0
            if on_page:
                on_page(page_count, effective_max)
            while has_more:
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

            # Save all works to DB
            for work in all_works:
                await crud.upsert_work(work)

            logger.info(f"Scraped {len(all_works)} works for {sec_user_id[:20]}...")
            return all_works

        finally:
            await self.interceptor.teardown()

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
