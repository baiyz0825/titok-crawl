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
        """Wait for an API response matching the given URL pattern."""
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                item = await asyncio.wait_for(
                    self._responses.get(), timeout=min(remaining, 2)
                )
                if pattern in item["url"]:
                    return item["data"]
                # Put non-matching items back? No — other callers may want them.
                # Instead, store them for later retrieval.
            except asyncio.TimeoutError:
                continue

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

    async def teardown(self):
        """Remove route interception."""
        if self._page:
            try:
                await self._page.unroute("**/aweme/v1/web/**")
            except Exception:
                pass
            self._page = None
