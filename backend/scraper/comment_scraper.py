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
from backend.db.models import Comment

logger = logging.getLogger(__name__)


class CommentScraper:
    def __init__(self):
        self.interceptor = ResponseInterceptor()

    async def scrape_comments(
        self,
        aweme_id: str,
        max_pages: int = 3,
        on_page: Callable | None = None,
        page: Page | None = None,
    ) -> list[Comment]:
        """Scrape comments for a work by navigating to the video page.

        Args:
            aweme_id: The work ID to scrape comments for
            max_pages: Maximum number of comment pages to scrape
            on_page: Callback function called after each page is scraped
            page: Optional Playwright Page object. If None, a new page will be created.

        Returns:
            List of Comment objects
        """
        # Determine if we need to manage the page lifecycle
        should_release = False
        if page is None:
            page = await engine.get_page()
            should_release = True
            logger.debug(f"Created new page for comment scraping: {aweme_id}")
        else:
            logger.debug(f"Using provided page for comment scraping: {aweme_id}")

        # Setup interceptor - use class instance for self-managed pages, new instance for external pages
        if should_release:
            # Self-managed page: use class interceptor
            self.interceptor.clear()
            await self.interceptor.setup(page)
            interceptor = self.interceptor
        else:
            # External page: create temporary interceptor to avoid conflicts
            interceptor = ResponseInterceptor()
            interceptor.clear()
            await interceptor.setup(page)

        all_comments = []
        # Track parent comments that need full reply fetching
        parents_needing_replies: list[tuple[str, int, int]] = []  # (comment_id, reply_total, inline_count)
        page_count = 0

        try:
            # Navigate to the work detail page
            url = f"{settings.DOUYIN_BASE_URL}/video/{aweme_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                logger.error(f"Failed to load video page (captcha timeout): {aweme_id}")
                return []

            # Wait for initial comments API response
            data = await interceptor.wait_for("comment/list", timeout=15)
            if data:
                comments = self._parse_comments(data, aweme_id)
                all_comments.extend(comments)
                self._collect_parents_needing_replies(data, parents_needing_replies)
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

                data = await interceptor.wait_for("comment/list", timeout=10)
                if not data:
                    break

                comments = self._parse_comments(data, aweme_id)
                if not comments:
                    break

                all_comments.extend(comments)
                self._collect_parents_needing_replies(data, parents_needing_replies)
                page_count += 1
                has_more = data.get("has_more", 0)
                if on_page:
                    on_page(page_count, max_pages)
                logger.info(f"Comments page {page_count}: got {len(comments)} (total: {len(all_comments)})")

            # Fetch full replies for comments that have more replies than inline preview
            if parents_needing_replies:
                logger.info(f"Fetching full replies for {len(parents_needing_replies)} comments")
                reply_comments = await self._fetch_all_replies(page, aweme_id, parents_needing_replies)
                all_comments.extend(reply_comments)
                logger.info(f"Fetched {len(reply_comments)} additional reply comments")

            # Save to DB
            for comment in all_comments:
                await crud.upsert_comment(comment)

            logger.info(f"Scraped {len(all_comments)} comments for {aweme_id}")
            return all_comments

        finally:
            await interceptor.teardown()
            if should_release:
                # Only close pages we created ourselves
                try:
                    if not page.is_closed():
                        await page.close()
                        logger.debug(f"Closed self-managed page for comment scraping")
                except Exception as e:
                    logger.warning(f"Failed to close page: {e}")

    def _collect_parents_needing_replies(
        self, data: dict, parents: list[tuple[str, int, int]]
    ):
        """Check each comment: if reply_comment_total > inline reply count, mark for fetching."""
        for item in data.get("comments", []):
            cid = str(item.get("cid", ""))
            reply_total = item.get("reply_comment_total", 0)
            inline_replies = item.get("reply_comment", []) or []
            if reply_total > len(inline_replies):
                parents.append((cid, reply_total, len(inline_replies)))

    async def _fetch_all_replies(
        self, page, aweme_id: str, parents: list[tuple[str, int, int]]
    ) -> list[Comment]:
        """Fetch complete reply threads via comment/list/reply API using page.evaluate."""
        all_replies = []
        for i, (comment_id, reply_total, inline_count) in enumerate(parents):
            cursor = 0
            fetched = 0
            max_reply_pages = 20  # safety limit

            logger.info(f"Fetching replies for comment {comment_id}: {reply_total} total, {inline_count} inline")

            for reply_page in range(max_reply_pages):
                # Rate limiting: longer delay every few pages
                if reply_page > 0:
                    delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                    await asyncio.sleep(delay)

                # Longer pause every 3-5 pages
                if reply_page > 0 and reply_page % random.randint(3, 5) == 0:
                    long_pause = random.uniform(5, 10)
                    logger.debug(f"Long pause: {long_pause:.1f}s")
                    await asyncio.sleep(long_pause)

                # Check captcha
                if await engine.detect_captcha(page):
                    resolved = await engine.wait_for_captcha_resolve(page)
                    if not resolved:
                        break

                # Use page.evaluate to call the reply API directly
                reply_url = (
                    f"https://www.douyin.com/aweme/v1/web/comment/list/reply/"
                    f"?item_id={aweme_id}&comment_id={comment_id}"
                    f"&cursor={cursor}&count=20&item_type=0"
                )
                try:
                    resp_data = await page.evaluate(f"""
                        async () => {{
                            const resp = await fetch("{reply_url}", {{
                                credentials: 'include',
                                headers: {{
                                    'referer': 'https://www.douyin.com/video/{aweme_id}',
                                    'accept': 'application/json'
                                }}
                            }});
                            return await resp.json();
                        }}
                    """)
                except Exception as e:
                    logger.warning(f"Failed to fetch replies for {comment_id}: {e}")
                    break

                if not resp_data or resp_data.get("status_code") != 0:
                    break

                reply_list = resp_data.get("comments", [])
                if not reply_list:
                    break

                for reply_item in reply_list:
                    try:
                        reply = self._parse_single_comment(
                            reply_item, aweme_id, parent_comment_id=comment_id
                        )
                        all_replies.append(reply)
                        fetched += 1
                    except Exception as e:
                        logger.warning(f"Failed to parse reply: {e}")

                has_more = resp_data.get("has_more", 0)
                cursor = resp_data.get("cursor", cursor + 20)

                if not has_more:
                    break

            logger.info(f"Comment {comment_id}: fetched {fetched} replies (expected ~{reply_total - inline_count} extra)")

        return all_replies

    def _parse_comments(self, data: dict, aweme_id: str) -> list[Comment]:
        """Parse comments from API response, including nested replies."""
        comment_list = data.get("comments", [])
        if not comment_list:
            return []

        comments = []
        for item in comment_list:
            try:
                comment = self._parse_single_comment(item, aweme_id)
                comments.append(comment)
                # Parse inline reply comments (sub-comments nested under parent)
                reply_comments = item.get("reply_comment", [])
                if reply_comments:
                    for reply_item in reply_comments:
                        try:
                            reply = self._parse_single_comment(
                                reply_item, aweme_id, parent_comment_id=comment.comment_id
                            )
                            comments.append(reply)
                        except Exception as e:
                            logger.warning(f"Failed to parse reply comment: {e}")
            except Exception as e:
                logger.warning(f"Failed to parse comment: {e}")
        return comments

    def _parse_single_comment(self, item: dict, aweme_id: str, parent_comment_id: str | None = None) -> Comment:
        cid = str(item.get("cid", ""))
        user = item.get("user", {})
        create_time = item.get("create_time", 0)

        # Determine parent: explicit param > reply_id field from API
        reply_to = parent_comment_id
        if not reply_to:
            reply_id = str(item.get("reply_id", "0"))
            if reply_id and reply_id != "0":
                reply_to = reply_id

        return Comment(
            comment_id=cid,
            aweme_id=aweme_id,
            user_uid=str(user.get("uid", "")) if user.get("uid") else "",
            user_nickname=user.get("nickname", ""),
            user_sec_uid=user.get("sec_uid", ""),
            user_avatar=user.get("avatar_thumb", {}).get("url_list", [""])[0]
                if isinstance(user.get("avatar_thumb"), dict) else "",
            content=item.get("text", ""),
            digg_count=item.get("digg_count", 0),
            reply_count=item.get("reply_comment_total", 0),
            reply_to=reply_to,
            create_time=datetime.fromtimestamp(create_time) if create_time else None,
            ip_label=item.get("ip_label", ""),
        )
