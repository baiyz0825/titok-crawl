import json
import logging
from datetime import datetime

from backend.scraper.user_scraper import UserScraper
from backend.scraper.search_scraper import SearchScraper
from backend.scraper.media_downloader import MediaDownloader
from backend.scraper.comment_scraper import CommentScraper
from backend.scraper.speech_recognizer import SpeechRecognizer
from backend.db import crud
from backend.queue.progress import progress_manager

logger = logging.getLogger(__name__)


class TaskWorker:
    """Maps task types to scraper methods and executes them."""

    def __init__(self):
        self.user_scraper = UserScraper()
        self.search_scraper = SearchScraper()
        self.media_downloader = MediaDownloader()
        self.comment_scraper = CommentScraper()
        self.speech_recognizer = SpeechRecognizer()

    async def execute(self, task_id: int, task_type: str, target: str, params: str | None) -> dict:
        """Execute a task and return result summary."""
        parsed_params = json.loads(params) if params else {}

        if task_type == "user_profile":
            return await self._scrape_profile(task_id, target)
        elif task_type == "user_works":
            return await self._scrape_works(task_id, target, parsed_params)
        elif task_type == "user_all":
            return await self._scrape_all(task_id, target, parsed_params)
        elif task_type == "search":
            return await self._search(task_id, target, parsed_params)
        elif task_type == "media_download":
            return await self._download_media(task_id, target, parsed_params)
        elif task_type == "comments":
            return await self._scrape_comments(task_id, target, parsed_params)
        elif task_type == "work_info":
            return await self._refresh_work_info(task_id, target, parsed_params)
        elif task_type == "speech_recognition":
            return await self._speech_recognize(task_id, target, parsed_params)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    async def _scrape_profile(self, task_id: int, sec_user_id: str) -> dict:
        progress_manager.update(task_id, 0.1, "采集用户资料", f"正在获取 {sec_user_id}")
        user = await self.user_scraper.scrape_profile(sec_user_id)
        progress_manager.update(task_id, 1.0, "完成", f"用户 {user.nickname if user else 'unknown'}")
        if user:
            return {"nickname": user.nickname, "follower_count": user.follower_count}
        return {"error": "User not found"}

    async def _scrape_works(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        max_pages = params.get("max_pages")
        progress_manager.update(task_id, 0.05, "开始采集作品", f"用户 {sec_user_id}")

        # Wrap scrape_works to track page progress
        works = await self.user_scraper.scrape_works(
            sec_user_id, max_pages=max_pages,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.1 + 0.8 * page_num / max(total, 1), 0.9),
                f"采集第 {page_num} 页",
                f"已获取作品数据"
            )
        )

        progress_manager.update(task_id, 0.95, "保存数据", f"共 {len(works)} 个作品")
        progress_manager.update(task_id, 1.0, "完成", f"共采集 {len(works)} 个作品")
        return {
            "count": len(works),
            "types": {
                "video": sum(1 for w in works if w.type == "video"),
                "note": sum(1 for w in works if w.type == "note"),
            },
        }

    async def _scrape_all(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        progress_manager.update(task_id, 0.05, "采集用户资料", sec_user_id)
        user = await self.user_scraper.scrape_profile(sec_user_id)

        progress_manager.update(task_id, 0.2, "采集作品列表", sec_user_id)
        max_pages = params.get("max_pages")
        works = await self.user_scraper.scrape_works(
            sec_user_id, max_pages=max_pages,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.2 + 0.4 * page_num / max(total, 1), 0.6),
                f"采集作品第 {page_num} 页",
                ""
            )
        )

        download_count = 0
        if params.get("download_media", False) and works:
            for i, work in enumerate(works):
                progress_manager.update(
                    task_id,
                    0.6 + 0.35 * (i + 1) / len(works),
                    f"下载媒体 {i+1}/{len(works)}",
                    work.aweme_id
                )
                await self.media_downloader.download_work_media(
                    work.aweme_id, sec_user_id, work.extra_data
                )
                download_count += 1

        progress_manager.update(task_id, 1.0, "完成", "")
        return {
            "nickname": user.nickname if user else None,
            "works_count": len(works),
            "media_downloaded": download_count,
        }

    async def _search(self, task_id: int, keyword: str, params: dict) -> dict:
        search_type = params.get("search_type", "user")
        progress_manager.update(task_id, 0.1, "搜索中", f"关键词: {keyword}")
        results = await self.search_scraper.search(keyword, search_type)
        progress_manager.update(task_id, 1.0, "完成", f"找到 {len(results)} 个结果")
        return {"keyword": keyword, "type": search_type, "count": len(results), "results": results}

    async def _download_media(self, task_id: int, aweme_id: str, params: dict) -> dict:
        sec_user_id = params.get("sec_user_id", "unknown")
        extra_data = params.get("extra_data")
        progress_manager.update(task_id, 0.1, "下载媒体", aweme_id)
        await self.media_downloader.download_work_media(aweme_id, sec_user_id, extra_data)
        progress_manager.update(task_id, 1.0, "完成", "")
        return {"aweme_id": aweme_id, "status": "completed"}

    async def _scrape_comments(self, task_id: int, aweme_id: str, params: dict) -> dict:
        max_pages = params.get("max_pages", 3)
        progress_manager.update(task_id, 0.05, "开始采集评论", aweme_id)
        comments = await self.comment_scraper.scrape_comments(
            aweme_id, max_pages=max_pages,
            on_page=lambda p, t: progress_manager.update(
                task_id, min(0.1 + 0.8 * p / max(t, 1), 0.9),
                f"采集评论第 {p} 页", ""
            )
        )
        progress_manager.update(task_id, 1.0, "完成", f"共 {len(comments)} 条评论")
        return {"aweme_id": aweme_id, "count": len(comments)}

    async def _refresh_work_info(self, task_id: int, aweme_id: str, params: dict) -> dict:
        """Re-scrape a single work's info (title, stats) by visiting its page."""
        sec_user_id = params.get("sec_user_id", "")
        progress_manager.update(task_id, 0.1, "刷新作品信息", aweme_id)

        # Navigate to the work page and intercept the detail API
        from backend.scraper.interceptor import ResponseInterceptor
        from backend.scraper.engine import engine
        from backend.config import settings
        from backend.db.models import Work

        interceptor = ResponseInterceptor()
        page = await engine.get_page()
        interceptor.clear()
        await interceptor.setup(page)

        try:
            url = f"{settings.DOUYIN_BASE_URL}/video/{aweme_id}"
            ok = await engine.safe_goto(page, url)
            if not ok:
                return {"error": "Failed to load page (captcha)"}

            progress_manager.update(task_id, 0.5, "解析作品数据", aweme_id)

            data = await interceptor.wait_for("aweme/detail", timeout=15)
            if not data:
                # Fallback: try aweme/v1/web/detail
                data = await interceptor.wait_for("detail", timeout=5)

            if data:
                aweme_detail = data.get("aweme_detail", data)
                stats = aweme_detail.get("statistics", {})
                work = Work(
                    aweme_id=aweme_id,
                    sec_user_id=sec_user_id or aweme_detail.get("author", {}).get("sec_uid", ""),
                    type="video" if aweme_detail.get("aweme_type", 0) in (0, 4) else "note",
                    title=aweme_detail.get("desc", ""),
                    cover_url=aweme_detail.get("video", {}).get("cover", {}).get("url_list", [""])[0]
                        if isinstance(aweme_detail.get("video", {}).get("cover"), dict) else "",
                    duration=aweme_detail.get("video", {}).get("duration", 0),
                    digg_count=stats.get("digg_count", 0),
                    comment_count=stats.get("comment_count", 0),
                    share_count=stats.get("share_count", 0),
                    collect_count=stats.get("collect_count", 0),
                    play_count=stats.get("play_count", 0),
                )
                await crud.upsert_work(work)
                progress_manager.update(task_id, 1.0, "完成", f"已更新作品信息")
                return {"aweme_id": aweme_id, "title": work.title, "digg_count": work.digg_count}
            else:
                progress_manager.update(task_id, 1.0, "完成", "未获取到数据")
                return {"aweme_id": aweme_id, "error": "No detail data intercepted"}
        finally:
            await interceptor.teardown()

    async def _speech_recognize(self, task_id: int, aweme_id: str, params: dict) -> dict:
        """Recognize speech from a downloaded video."""
        progress_manager.update(task_id, 0.1, "查找视频文件", aweme_id)

        # Find the local video file
        media_files = await crud.get_media_files(aweme_id)
        video_path = None
        for mf in media_files:
            if mf.media_type == "video" and mf.download_status == "completed" and mf.local_path:
                from pathlib import Path
                if Path(mf.local_path).exists():
                    video_path = mf.local_path
                    break

        if not video_path:
            progress_manager.update(task_id, 1.0, "完成", "未找到本地视频文件")
            return {"aweme_id": aweme_id, "error": "No local video file found"}

        progress_manager.update(task_id, 0.3, "语音识别中", aweme_id)
        text = await self.speech_recognizer.recognize(video_path)

        if text:
            await crud.update_work_transcript(aweme_id, text)
            progress_manager.update(task_id, 1.0, "完成", f"识别 {len(text)} 字")
            return {"aweme_id": aweme_id, "transcript_length": len(text)}
        else:
            progress_manager.update(task_id, 1.0, "完成", "未识别到语音")
            return {"aweme_id": aweme_id, "transcript": None}
