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

    async def _check_cancelled(self, task_id: int) -> bool:
        """Check if task has been cancelled."""
        task = await crud.get_task(task_id)
        return task and task.status == "cancelled"

    async def execute(self, task_id: int, task_type: str, target: str, params: str | None) -> dict:
        """Execute a task and return result summary."""
        parsed_params = json.loads(params) if params else {}

        if task_type == "user_profile":
            return await self._scrape_profile(task_id, target)
        elif task_type == "user_works":
            return await self._scrape_works(task_id, target, parsed_params)
        elif task_type == "user_all":
            return await self._scrape_all(task_id, target, parsed_params)
        elif task_type == "user_likes":
            return await self._scrape_likes(task_id, target, parsed_params)
        elif task_type == "user_favorites":
            return await self._scrape_favorites(task_id, target, parsed_params)
        elif task_type == "user_following":
            return await self._scrape_following(task_id, target, parsed_params)
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
        user = await self.user_scraper.scrape_profile(task_id, sec_user_id)
        progress_manager.update(task_id, 1.0, "完成", f"用户 {user.nickname if user else 'unknown'}")
        if user:
            return {"nickname": user.nickname, "follower_count": user.follower_count}
        return {"error": "User not found"}

    async def _scrape_works(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        max_count = params.get("max_count")
        scrape_comments = params.get("scrape_comments", False)
        refresh_info = params.get("refresh_info", False)
        download_media = params.get("download_media", False)
        logger.info(f"[Task {task_id}] Starting scrape_works for {sec_user_id}, max_count={max_count}, scrape_comments={scrape_comments}, refresh_info={refresh_info}, download_media={download_media}")
        progress_manager.update(task_id, 0.05, "开始采集作品", f"用户 {sec_user_id}")

        # Wrap scrape_works to track page progress
        works = await self.user_scraper.scrape_works(
            task_id, sec_user_id, max_count=max_count,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.1 + 0.8 * page_num / max(total, 1), 0.9),
                f"采集第 {page_num} 页",
                f"已获取作品数据"
            )
        )

        logger.info(f"[Task {task_id}] Scraped {len(works)} works, starting upsert to DB")
        # Upsert all works to DB
        for i, work in enumerate(works):
            await crud.upsert_work(work)
            if (i + 1) % 10 == 0:
                logger.info(f"[Task {task_id}] Upserted {i + 1}/{len(works)} works")

        progress_manager.update(task_id, 0.95, "保存数据", f"共 {len(works)} 个作品")

        # Refresh work info if requested (re-visit each work page for updated stats)
        refreshed_count = 0
        if refresh_info and works:
            logger.info(f"[Task {task_id}] Starting work info refresh for {len(works)} works")
            progress_manager.update(task_id, 0.96, "刷新作品信息", f"准备刷新 {len(works)} 个作品的统计信息")
            for i, work in enumerate(works):
                try:
                    result = await self._refresh_work_info(task_id, work.aweme_id, {"sec_user_id": sec_user_id})
                    if result and not result.get("error"):
                        refreshed_count += 1
                        if (i + 1) % 10 == 0:
                            logger.info(f"[Task {task_id}] Refreshed {i + 1}/{len(works)} work info")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to refresh info for {work.aweme_id}: {e}")

        # Scrape comments if requested
        comments_count = 0
        if scrape_comments and works:
            logger.info(f"[Task {task_id}] Starting comment scraping for {len(works)} works")
            progress_manager.update(task_id, 0.97, "采集评论", f"准备采集 {len(works)} 个作品的评论")
            for i, work in enumerate(works):
                try:
                    comments = await self.comment_scraper.scrape_comments(
                        work.aweme_id, max_pages=3, on_page=None
                    )
                    # Save comments
                    for comment in comments:
                        await crud.upsert_comment(comment)
                    comments_count += len(comments)
                    logger.info(f"[Task {task_id}] Scraped {len(comments)} comments for {work.aweme_id}")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to scrape comments for {work.aweme_id}: {e}")

        # Download media if requested
        download_count = 0
        if download_media and works:
            logger.info(f"[Task {task_id}] Starting media download for {len(works)} works")
            progress_manager.update(task_id, 0.98, "下载媒体", f"准备下载 {len(works)} 个作品的媒体文件")
            for i, work in enumerate(works):
                try:
                    progress_manager.update(
                        task_id,
                        0.98 + 0.01 * (i + 1) / len(works),
                        f"下载媒体 {i+1}/{len(works)}",
                        work.aweme_id
                    )
                    await self.media_downloader.download_work_media(
                        work.aweme_id, sec_user_id, work.extra_data
                    )
                    download_count += 1
                    if (i + 1) % 10 == 0:
                        logger.info(f"[Task {task_id}] Downloaded media for {i + 1}/{len(works)} works")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to download media for {work.aweme_id}: {e}")

        extra_info = []
        if refreshed_count > 0:
            extra_info.append(f"刷新 {refreshed_count} 个作品信息")
        if comments_count > 0:
            extra_info.append(f"{comments_count} 条评论")
        if download_count > 0:
            extra_info.append(f"下载 {download_count} 个媒体")

        progress_manager.update(task_id, 1.0, "完成", f"共采集 {len(works)} 个作品" + (extra_info.join(", ") if extra_info else ""))
        logger.info(f"[Task {task_id}] Completed: {len(works)} works upserted, {refreshed_count} refreshed, {comments_count} comments scraped, {download_count} media downloaded")
        return {
            "count": len(works),
            "refreshed_count": refreshed_count,
            "comments_count": comments_count,
            "media_downloaded": download_count,
            "types": {
                "video": sum(1 for w in works if w.type == "video"),
                "note": sum(1 for w in works if w.type == "note"),
            },
        }

    async def _scrape_all(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        progress_manager.update(task_id, 0.05, "采集用户资料", sec_user_id)
        user = await self.user_scraper.scrape_profile(task_id, sec_user_id)

        progress_manager.update(task_id, 0.2, "采集作品列表", sec_user_id)
        max_count = params.get("max_count")
        scrape_comments = params.get("scrape_comments", False)
        refresh_info = params.get("refresh_info", False)
        works = await self.user_scraper.scrape_works(
            task_id, sec_user_id, max_count=max_count,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.2 + 0.4 * page_num / max(total, 1), 0.6),
                f"采集作品第 {page_num} 页",
                ""
            )
        )

        # Upsert all works to DB
        for work in works:
            await crud.upsert_work(work)

        # Refresh work info if requested
        refreshed_count = 0
        if refresh_info and works:
            progress_manager.update(task_id, 0.61, "刷新作品信息", f"准备刷新 {len(works)} 个作品")
            for i, work in enumerate(works):
                try:
                    result = await self._refresh_work_info(task_id, work.aweme_id, {"sec_user_id": sec_user_id})
                    if result and not result.get("error"):
                        refreshed_count += 1
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to refresh info for {work.aweme_id}: {e}")

        # Download media if requested
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

        # Scrape comments if requested
        comments_count = 0
        if scrape_comments and works:
            progress_manager.update(task_id, 0.96, "采集评论", f"准备采集 {len(works)} 个作品的评论")
            for i, work in enumerate(works):
                try:
                    comments = await self.comment_scraper.scrape_comments(
                        work.aweme_id, max_pages=3, on_page=None
                    )
                    for comment in comments:
                        await crud.upsert_comment(comment)
                    comments_count += len(comments)
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to scrape comments for {work.aweme_id}: {e}")

        progress_manager.update(task_id, 1.0, "完成", "")
        return {
            "nickname": user.nickname if user else None,
            "works_count": len(works),
            "media_downloaded": download_count,
            "comments_count": comments_count,
            "refreshed_count": refreshed_count,
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

    async def _scrape_likes(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape current user's liked videos with upsert (update if exists)."""
        max_pages = params.get("max_pages")
        max_count = params.get("max_count")
        collect_creators = params.get("collect_creators", False)
        download_media = params.get("download_media", False)
        scrape_comments = params.get("scrape_comments", False)
        progress_manager.update(task_id, 0.05, "开始采集喜欢的视频", "")

        works = await self.user_scraper.scrape_likes(
            task_id, sec_user_id, max_pages=max_pages, max_count=max_count,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.1 + 0.6 * page_num / max(total, 1), 0.7),
                f"采集第 {page_num} 页",
                f"已获取喜欢的视频数据"
            ),
            check_cancelled=lambda: self._check_cancelled(task_id)
        )

        # Upsert all works (update if exists, insert if new)
        new_count = 0
        updated_count = 0
        processed_works = []
        for work in works:
            existing = await crud.get_work(work.aweme_id)
            if existing:
                updated_count += 1
            else:
                new_count += 1
            await crud.upsert_work(work)
            processed_works.append(work)
            # Limit max count if specified
            if max_count and len(processed_works) >= max_count:
                break

        # Download media if requested
        download_count = 0
        if download_media and processed_works:
            logger.info(f"[Task {task_id}] Starting media download for {len(processed_works)} liked works")
            progress_manager.update(task_id, 0.75, "下载媒体", f"准备下载 {len(processed_works)} 个作品的媒体文件")
            for i, work in enumerate(processed_works):
                # Check if task is cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled, stopping media download")
                    break

                try:
                    progress_manager.update(
                        task_id,
                        0.75 + 0.1 * (i + 1) / len(processed_works),
                        f"下载媒体 {i+1}/{len(processed_works)}",
                        work.aweme_id
                    )
                    await self.media_downloader.download_work_media(
                        work.aweme_id, work.sec_user_id, work.extra_data
                    )
                    download_count += 1
                    if (i + 1) % 10 == 0:
                        logger.info(f"[Task {task_id}] Downloaded media for {i + 1}/{len(processed_works)} liked works")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to download media for {work.aweme_id}: {e}")

        # Scrape comments if requested
        comments_count = 0
        if scrape_comments and processed_works:
            logger.info(f"[Task {task_id}] Starting comment scraping for {len(processed_works)} liked works")
            progress_manager.update(task_id, 0.86, "采集评论", f"准备采集 {len(processed_works)} 个作品的评论")
            for i, work in enumerate(processed_works):
                # Check if task is cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled, stopping comment scraping")
                    break

                try:
                    comments = await self.comment_scraper.scrape_comments(
                        work.aweme_id, max_pages=3, on_page=None
                    )
                    # Save comments
                    for comment in comments:
                        await crud.upsert_comment(comment)
                    comments_count += len(comments)
                    logger.info(f"[Task {task_id}] Scraped {len(comments)} comments for {work.aweme_id}")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to scrape comments for {work.aweme_id}: {e}")

        # Collect creators if requested
        creators_collected = 0
        if collect_creators and processed_works:
            # Collect unique author sec_user_ids
            author_ids = list(set(w.sec_user_id for w in processed_works))
            progress_manager.update(task_id, 0.91, "采集作者信息", f"准备采集 {len(author_ids)} 个作者信息")

            for i, author_id in enumerate(author_ids):
                try:
                    progress_manager.update(
                        task_id,
                        0.91 + 0.04 * (i + 1) / len(author_ids),
                        f"采集作者 {i+1}/{len(author_ids)}",
                        author_id
                    )
                    user = await self.user_scraper.scrape_profile(task_id, author_id)
                    if user:
                        await crud.upsert_user(user)
                        creators_collected += 1
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to collect creator {author_id}: {e}")

        extra_info = f"新增 {new_count} 个，更新 {updated_count} 个"
        if download_count > 0:
            extra_info += f"，下载 {download_count} 个媒体"
        if comments_count > 0:
            extra_info += f"，{comments_count} 条评论"
        if creators_collected > 0:
            extra_info += f"，采集作者 {creators_collected} 个"

        progress_manager.update(task_id, 1.0, "完成", f"共处理 {len(processed_works)} 个作品")
        return {
            "total": len(processed_works),
            "new": new_count,
            "updated": updated_count,
            "media_downloaded": download_count,
            "comments_count": comments_count,
            "creators_collected": creators_collected,
            "types": {
                "video": sum(1 for w in processed_works if w.type == "video"),
                "note": sum(1 for w in processed_works if w.type == "note"),
            },
        }

    async def _scrape_favorites(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape current user's favorite videos with upsert (update if exists)."""
        max_pages = params.get("max_pages")
        max_count = params.get("max_count")
        collect_creators = params.get("collect_creators", False)
        download_media = params.get("download_media", False)
        scrape_comments = params.get("scrape_comments", False)
        progress_manager.update(task_id, 0.05, "开始采集收藏的视频", "")

        works = await self.user_scraper.scrape_favorites(
            task_id, sec_user_id, max_pages=max_pages, max_count=max_count,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.1 + 0.6 * page_num / max(total, 1), 0.7),
                f"采集第 {page_num} 页",
                f"已获取收藏的视频数据"
            ),
            check_cancelled=lambda: self._check_cancelled(task_id)
        )

        # Upsert all works (update if exists, insert if new)
        new_count = 0
        updated_count = 0
        processed_works = []
        for work in works:
            existing = await crud.get_work(work.aweme_id)
            if existing:
                updated_count += 1
            else:
                new_count += 1
            await crud.upsert_work(work)
            # Automatically add to favorites
            await crud.add_favorite(work.aweme_id, work.sec_user_id)
            processed_works.append(work)
            # Limit max count if specified
            if max_count and len(processed_works) >= max_count:
                break

        # Download media if requested
        download_count = 0
        if download_media and processed_works:
            logger.info(f"[Task {task_id}] Starting media download for {len(processed_works)} favorite works")
            progress_manager.update(task_id, 0.75, "下载媒体", f"准备下载 {len(processed_works)} 个作品的媒体文件")
            for i, work in enumerate(processed_works):
                # Check if task is cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled, stopping media download")
                    break

                try:
                    progress_manager.update(
                        task_id,
                        0.75 + 0.1 * (i + 1) / len(processed_works),
                        f"下载媒体 {i+1}/{len(processed_works)}",
                        work.aweme_id
                    )
                    await self.media_downloader.download_work_media(
                        work.aweme_id, work.sec_user_id, work.extra_data
                    )
                    download_count += 1
                    if (i + 1) % 10 == 0:
                        logger.info(f"[Task {task_id}] Downloaded media for {i + 1}/{len(processed_works)} favorite works")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to download media for {work.aweme_id}: {e}")

        # Scrape comments if requested
        comments_count = 0
        if scrape_comments and processed_works:
            logger.info(f"[Task {task_id}] Starting comment scraping for {len(processed_works)} favorite works")
            progress_manager.update(task_id, 0.86, "采集评论", f"准备采集 {len(processed_works)} 个作品的评论")
            for i, work in enumerate(processed_works):
                # Check if task is cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled, stopping comment scraping")
                    break

                try:
                    comments = await self.comment_scraper.scrape_comments(
                        work.aweme_id, max_pages=3, on_page=None
                    )
                    # Save comments
                    for comment in comments:
                        await crud.upsert_comment(comment)
                    comments_count += len(comments)
                    logger.info(f"[Task {task_id}] Scraped {len(comments)} comments for {work.aweme_id}")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to scrape comments for {work.aweme_id}: {e}")

        # Collect creators if requested
        creators_collected = 0
        if collect_creators and processed_works:
            # Collect unique author sec_user_ids
            author_ids = list(set(w.sec_user_id for w in processed_works))
            progress_manager.update(task_id, 0.91, "采集作者信息", f"准备采集 {len(author_ids)} 个作者信息")

            for i, author_id in enumerate(author_ids):
                try:
                    progress_manager.update(
                        task_id,
                        0.91 + 0.04 * (i + 1) / len(author_ids),
                        f"采集作者 {i+1}/{len(author_ids)}",
                        author_id
                    )
                    user = await self.user_scraper.scrape_profile(task_id, author_id)
                    if user:
                        await crud.upsert_user(user)
                        creators_collected += 1
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to collect creator {author_id}: {e}")

        extra_info = f"新增 {new_count} 个，更新 {updated_count} 个"
        if download_count > 0:
            extra_info += f"，下载 {download_count} 个媒体"
        if comments_count > 0:
            extra_info += f"，{comments_count} 条评论"
        if creators_collected > 0:
            extra_info += f"，采集作者 {creators_collected} 个"

        progress_manager.update(task_id, 1.0, "完成", f"共处理 {len(processed_works)} 个作品")
        return {
            "total": len(processed_works),
            "new": new_count,
            "updated": updated_count,
            "media_downloaded": download_count,
            "comments_count": comments_count,
            "creators_collected": creators_collected,
            "types": {
                "video": sum(1 for w in processed_works if w.type == "video"),
                "note": sum(1 for w in processed_works if w.type == "note"),
            },
        }

    async def _scrape_following(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape user's following list with optional recursive collection."""
        max_count = params.get("max_count")
        collect_profile = params.get("collect_profile", False)
        recursive = params.get("recursive", False)
        recursive_depth = params.get("recursive_depth", 1)

        logger.info(f"[Task {task_id}] Starting scrape_following for {sec_user_id}, max_count={max_count}, collect_profile={collect_profile}, recursive={recursive}, depth={recursive_depth}")
        progress_manager.update(task_id, 0.05, "开始采集关注列表", f"用户 {sec_user_id[:20]}...")

        # Use a set to track processed users and avoid duplicates
        processed_users = set()
        all_users_data = []

        # Recursive collection function
        async def collect_following_recursive(target_id: str, current_depth: int):
            if current_depth > recursive_depth:
                return

            if target_id in processed_users:
                return

            processed_users.add(target_id)
            progress_manager.update(task_id, 0.1, f"采集关注列表 (深度 {current_depth}/{recursive_depth})", f"已处理 {len(processed_users)} 个用户")

            # Get following list for this user
            following_users = await self.user_scraper.scrape_following(
                task_id, target_id, max_count=None,  # No limit per user
                on_page=None
            )

            logger.info(f"[Task {task_id}] Found {len(following_users)} following for {target_id[:20]}...")

            for user_info in following_users:
                following_id = user_info["sec_user_id"]

                # Collect profile if requested
                if collect_profile and following_id not in processed_users:
                    try:
                        progress_manager.update(task_id, 0.1, f"采集用户资料 ({len(all_users_data)})", user_info["nickname"] or following_id[:20])
                        user = await self.user_scraper.scrape_profile(task_id, following_id)
                        if user:
                            await crud.upsert_user(user)
                            all_users_data.append(user_info)
                            logger.info(f"[Task {task_id}] Saved profile for {user.nickname} ({following_id[:20]}...)")
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] Failed to scrape profile for {following_id[:20]}: {e}")
                        all_users_data.append(user_info)  # Add basic info even if profile scrape fails
                else:
                    all_users_data.append(user_info)

                # Recursive collection
                if recursive and current_depth < recursive_depth:
                    await collect_following_recursive(following_id, current_depth + 1)

        # Start collection
        await collect_following_recursive(sec_user_id, 1)

        progress_manager.update(task_id, 0.95, "保存数据", f"共采集 {len(all_users_data)} 个关注用户")
        progress_manager.update(task_id, 1.0, "完成", f"共采集 {len(all_users_data)} 个用户，深度 {recursive_depth}")

        logger.info(f"[Task {task_id}] Completed: {len(all_users_data)} users collected, {len(processed_users)} unique users processed")

        return {
            "total": len(all_users_data),
            "unique": len(processed_users),
            "collect_profile": collect_profile,
            "recursive": recursive,
            "depth": recursive_depth,
        }
