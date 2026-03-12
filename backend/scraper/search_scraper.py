import asyncio
import logging
import random

from backend.config import settings
from backend.scraper.engine import engine
from backend.scraper.interceptor import ResponseInterceptor

logger = logging.getLogger(__name__)


class SearchScraper:
    def __init__(self):
        self.interceptor = ResponseInterceptor()

    async def search(self, keyword: str, search_type: str = "user") -> list[dict]:
        """Search Douyin for users or works by keyword."""
        page = await engine.get_page()
        self.interceptor.clear()
        await self.interceptor.setup(page)

        try:
            # Navigate to search page
            from urllib.parse import quote
            search_url = f"{settings.DOUYIN_BASE_URL}/search/{quote(keyword)}?type={search_type}"
            ok = await engine.safe_goto(page, search_url)
            if not ok:
                logger.error("Failed to load search page (captcha timeout)")
                return []

            # Wait for search results
            data = await self.interceptor.wait_for("discover/search", timeout=15)
            if not data:
                logger.warning(f"No search results for '{keyword}'")
                return []

            results = self._parse_search_results(data, search_type)
            logger.info(f"Search '{keyword}': found {len(results)} results")
            return results

        finally:
            await self.interceptor.teardown()

    def _parse_search_results(self, data: dict, search_type: str) -> list[dict]:
        """Parse search results from API response."""
        results = []
        items = data.get("data", [])

        for item in items:
            try:
                if search_type == "user":
                    user_info = item.get("user_list", [{}])[0] if "user_list" in item else item
                    user = user_info.get("user_info", user_info)
                    results.append({
                        "sec_user_id": user.get("sec_uid", ""),
                        "nickname": user.get("nickname", ""),
                        "follower_count": user.get("follower_count", 0),
                        "signature": user.get("signature", ""),
                    })
                else:
                    aweme = item.get("aweme_info", item)
                    results.append({
                        "aweme_id": str(aweme.get("aweme_id", "")),
                        "desc": aweme.get("desc", ""),
                        "author": aweme.get("author", {}).get("nickname", ""),
                    })
            except Exception as e:
                logger.warning(f"Failed to parse search result: {e}")
                continue

        return results
