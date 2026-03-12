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
from backend.db.models import Comment

logger = logging.getLogger(__name__)


class CommentScraper:
    def __init__(self):
        self.interceptor = ResponseInterceptor()

    async def scrape_comments(
        self, aweme_id: str, max_pages: int = 3, on_page: Callable | None = None,
    ) -> list[Comment]:
        """Scrape comments for a work by navigating to the video page."""
        page = await engine.get_page()
        self.interceptor.clear()
        await self.interceptor.setup(page)

        all_comments = []
        page_count = 0

        try:
            # Navigate to the work detail page
            url = f"{settings.DOUYIN_BASE_URL}/video/{aweme_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error(f"Failed to load video page (captcha timeout): {aweme_id}")
                return []

            # Wait for initial comments API response
            data = await self.interceptor.wait_for("comment/list", timeout=15)
            if data:
                comments = self._parse_comments(data, aweme_id)
                all_comments.extend(comments)
                page_count += 1
                if on_page:
                    on_page(page_count, max_pages)
                logger.info(f"Comments page {page_count}: got {len(comments)} comments")

            # Pagination
            has_more = data.get("has_more", 0) if data else 0
            while has_more and page_count < max_pages:
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

                # Check for captcha during pagination
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        break

                # Scroll down to load more comments
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

                data = await self.interceptor.wait_for("comment/list", timeout=10)
                if not data:
                    break

                comments = self._parse_comments(data, aweme_id)
                if not comments:
                    break

                all_comments.extend(comments)
                page_count += 1
                has_more = data.get("has_more", 0)
                if on_page:
                    on_page(page_count, max_pages)
                logger.info(f"Comments page {page_count}: got {len(comments)} (total: {len(all_comments)})")

            # Save to DB
            for comment in all_comments:
                await crud.upsert_comment(comment)

            logger.info(f"Scraped {len(all_comments)} comments for {aweme_id}")
            return all_comments

        finally:
            await self.interceptor.teardown()

    def _parse_comments(self, data: dict, aweme_id: str) -> list[Comment]:
        """Parse comments from API response."""
        comment_list = data.get("comments", [])
        if not comment_list:
            return []

        comments = []
        for item in comment_list:
            try:
                comment = self._parse_single_comment(item, aweme_id)
                comments.append(comment)
            except Exception as e:
                logger.warning(f"Failed to parse comment: {e}")
        return comments

    def _parse_single_comment(self, item: dict, aweme_id: str) -> Comment:
        cid = str(item.get("cid", ""))
        user = item.get("user", {})
        create_time = item.get("create_time", 0)

        return Comment(
            comment_id=cid,
            aweme_id=aweme_id,
            user_nickname=user.get("nickname", ""),
            user_sec_uid=user.get("sec_uid", ""),
            user_avatar=user.get("avatar_thumb", {}).get("url_list", [""])[0]
                if isinstance(user.get("avatar_thumb"), dict) else "",
            content=item.get("text", ""),
            digg_count=item.get("digg_count", 0),
            reply_count=item.get("reply_comment_total", 0),
            create_time=datetime.fromtimestamp(create_time) if create_time else None,
            ip_label=item.get("ip_label", ""),
        )
