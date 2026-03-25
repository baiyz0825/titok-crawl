import asyncio
import json
import logging
from pathlib import Path

import httpx

from backend.config import settings
from backend.db import crud
from backend.db.models import MediaFile

logger = logging.getLogger(__name__)

# Reusable HTTP client for downloading
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.douyin.com/",
            },
        )
    return _client


class MediaDownloader:
    async def download_work_media(self, aweme_id: str, sec_user_id: str, extra_data: str | None):
        """Download all media for a work (video or images)."""
        if not extra_data:
            return

        data = json.loads(extra_data)
        video_urls = data.get("video_url", [])
        image_urls = data.get("images", [])

        if video_urls:
            await self.download_video(aweme_id, video_urls, sec_user_id)
        if image_urls:
            await self.download_images(aweme_id, image_urls, sec_user_id)

    async def download_video(self, aweme_id: str, urls: list[str], sec_user_id: str):
        """Download video file."""
        # Check if already downloaded
        existing = await crud.get_media_files(aweme_id)
        for mf in existing:
            if mf.media_type == "video" and mf.download_status == "completed":
                if mf.local_path and Path(mf.local_path).exists():
                    logger.debug(f"Video already downloaded: {aweme_id}")
                    return

        if not urls:
            return

        # Pick the first available URL
        url = urls[0] if isinstance(urls[0], str) else urls[0]

        # Create media file record
        dest_dir = settings.MEDIA_DIR / sec_user_id / "videos"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{aweme_id}.mp4"

        mf = MediaFile(
            aweme_id=aweme_id,
            media_type="video",
            url=url,
            local_path=str(dest_path),
            download_status="downloading",
        )
        file_id = await crud.create_media_file(mf)

        # Download
        success = await self._download_file(url, dest_path)
        if success:
            file_size = dest_path.stat().st_size
            await crud.update_media_file(
                file_id, download_status="completed", file_size=file_size
            )
            logger.info(f"Downloaded video: {aweme_id} ({file_size} bytes)")
        else:
            await crud.update_media_file(
                file_id, download_status="failed", retry_count=1
            )

    async def download_images(self, aweme_id: str, urls: list[str], sec_user_id: str):
        """Download all images for a note/image post."""
        if not urls:
            return

        # Check if already downloaded
        existing = await crud.get_media_files(aweme_id)
        completed_images = [mf for mf in existing if mf.media_type == "image" and mf.download_status == "completed"]
        if len(completed_images) >= len(urls):
            logger.debug(f"Images already downloaded: {aweme_id}")
            return

        dest_dir = settings.MEDIA_DIR / sec_user_id / "notes" / aweme_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        for i, url in enumerate(urls):
            if not url:
                continue

            ext = "jpg"  # Default extension
            dest_path = dest_dir / f"{i + 1}.{ext}"

            mf = MediaFile(
                aweme_id=aweme_id,
                media_type="image",
                url=url,
                local_path=str(dest_path),
                download_status="downloading",
            )
            file_id = await crud.create_media_file(mf)

            success = await self._download_file(url, dest_path)
            if success:
                file_size = dest_path.stat().st_size
                await crud.update_media_file(
                    file_id, download_status="completed", file_size=file_size
                )
                logger.info(f"Downloaded image: {aweme_id}/{i + 1} ({file_size} bytes)")
            else:
                await crud.update_media_file(
                    file_id, download_status="failed", retry_count=1
                )

    async def _download_file(self, url: str, dest: Path) -> bool:
        """Download a file from URL to local path."""
        try:
            client = await _get_client()
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    logger.warning(f"Download failed ({resp.status_code}): {url[:80]}")
                    return False
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

    async def retry_failed(self, limit: int = 10):
        """Retry downloading failed media files."""
        pending = await crud.get_pending_media_files(limit)
        for mf in pending:
            if mf.local_path:
                dest = Path(mf.local_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                success = await self._download_file(mf.url, dest)
                if success:
                    file_size = dest.stat().st_size
                    await crud.update_media_file(
                        mf.id, download_status="completed", file_size=file_size
                    )
                else:
                    await crud.update_media_file(
                        mf.id, download_status="failed", retry_count=(mf.retry_count or 0) + 1
                    )
