import asyncio
import json
import logging
import re
from playwright.async_api import Page, Route, Response

logger = logging.getLogger(__name__)


class ResponseInterceptor:
    """Intercepts API responses using page.route()."""

    def __init__(self):
        self._responses: asyncio.Queue[dict] = asyncio.Queue()
        self._page: Page | None = None

    async def setup(self, page: Page):
        """Register route interception on a page."""
        self._page = page
        await page.route("**/aweme/v1/web/**", self._on_route)

    async def _on_route(self, route: Route):
        """Intercept: let request pass through, capture the response."""
        try:
            response = await route.fetch()
            content_type = response.headers.get("content-type", "")

            if "json" in content_type or "application/json" in content_type:
                try:
                    body = await response.json()
                    url = route.request.url
                    await self._responses.put({"url": url, "data": body})
                    logger.debug(f"Intercepted: {url[:100]}")
                except Exception:
                    pass  # Non-JSON response, ignore

            await route.fulfill(response=response)
        except Exception as e:
            logger.warning(f"Route interception error: {e}")
            try:
                await route.continue_()
            except Exception:
                pass

    async def wait_for(self, pattern: str, timeout: float = 30) -> dict | None:
        """Wait for an API response matching the given URL pattern.

        Keeps non-matching items in a temporary buffer to avoid losing them.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        temp_buffer = []

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                item = await asyncio.wait_for(
                    self._responses.get(), timeout=min(remaining, 2)
                )
                if pattern in item["url"]:
                    # Found matching API - return it and put back buffered items
                    for buffered_item in temp_buffer:
                        await self._responses.put(buffered_item)
                    logger.debug(f"Found matching API: {pattern}")
                    return item["data"]
                else:
                    # Buffer non-matching items
                    temp_buffer.append(item)
                    logger.debug(f"Buffered non-matching API: {item['url'][:80]}...")
            except asyncio.TimeoutError:
                continue

        # Put back all buffered items before timeout
        for buffered_item in temp_buffer:
            await self._responses.put(buffered_item)

        logger.warning(f"Timeout waiting for API pattern: {pattern}")
        return None

    async def drain(self, pattern: str, timeout: float = 2) -> list[dict]:
        """Collect all queued responses matching pattern within timeout."""
        results = []
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                item = await asyncio.wait_for(
                    self._responses.get(), timeout=min(remaining, 0.5)
                )
                if pattern in item["url"]:
                    results.append(item["data"])
            except asyncio.TimeoutError:
                break

        return results

    def clear(self):
        """Clear all queued responses."""
        while not self._responses.empty():
            try:
                self._responses.get_nowait()
            except asyncio.QueueEmpty:
                break

    def get_captured_urls(self) -> list[str]:
        """Get list of all captured API URLs (for debugging)."""
        urls = []
        # 创建一个临时队列来遍历
        temp_items = []
        while not self._responses.empty():
            try:
                item = self._responses.get_nowait()
                temp_items.append(item)
                urls.append(item.get("url", ""))
            except asyncio.QueueEmpty:
                break

        # 把所有元素放回队列
        for item in temp_items:
            try:
                self._responses.put_nowait(item)
            except:
                pass

        return urls

    async def teardown(self):
        """Remove route interception."""
        if self._page:
            try:
                await self._page.unroute("**/aweme/v1/web/**")
            except Exception:
                pass
            self._page = None
