import asyncio
import json
import logging
from datetime import datetime

from backend.config import settings
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

    async def _get_task_param(self, task_id: int, key: str, default=None):
        """Get current task parameter from database (supports dynamic updates)."""
        task = await crud.get_task(task_id)
        if not task or not task.params:
            return default
        try:
            params = json.loads(task.params)
            return params.get(key, default)
        except Exception:
            return default

    async def _resolve_sec_user_id(self, target: str) -> str | None:
        """Resolve target (uid or sec_user_id) to sec_user_id for Douyin API.

        Douyin API requires sec_user_id, but frontend may pass uid.
        This function looks up sec_user_id from database if uid is passed.
        """
        # If target looks like sec_user_id (starts with MS4wLjAB), use directly
        if target.startswith("MS4wLjAB"):
            return target

        # Try as uid (numeric format like 670059810022624)
        if target.isdigit():
            user = await crud.get_user_by_uid(target)
            if user:
                logger.info(f"Resolved uid {target} to sec_user_id {user.sec_user_id}")
                return user.sec_user_id

        # Fallback: try as sec_user_id directly
        user = await crud.get_user(target)
        if user:
            return user.sec_user_id

        # Not found in database, assume it's already a sec_user_id
        logger.warning(f"Target {target} not found in database, using as-is")
        return target

    async def execute(self, task_id: int, task_type: str, target: str, params: str | None) -> dict:
        """Execute a task and return result summary."""
        parsed_params = json.loads(params) if params else {}

        # Resolve target to sec_user_id for user-related tasks
        if task_type in ["user_profile", "user_works", "user_all", "user_likes", "user_favorites", "user_following"]:
            sec_user_id = await self._resolve_sec_user_id(target)
            if not sec_user_id:
                return {"error": f"Cannot resolve target {target} to sec_user_id"}
            target = sec_user_id

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
        speech_recognition = params.get("speech_recognition", False)
        logger.info(f"[Task {task_id}] Starting scrape_works for {sec_user_id}, max_count={max_count}, scrape_comments={scrape_comments}, refresh_info={refresh_info}, download_media={download_media}, speech_recognition={speech_recognition}")
        progress_manager.update(task_id, 0.05, "开始采集作品", f"用户 {sec_user_id}")

        # Wrap scrape_works to track page progress
        works = await self.user_scraper.scrape_works(
            task_id, sec_user_id, max_count=max_count,
            on_page=lambda page_num, total: progress_manager.update(
                task_id,
                min(0.1 + 0.8 * page_num / max(total, 1), 0.9),
                f"采集第 {page_num} 页",
                f"已获取作品数据"
            ),
            check_cancelled=lambda: self._check_cancelled(task_id),
            get_max_count=lambda: self._get_task_param(task_id, "max_count")
        )

        logger.info(f"[Task {task_id}] Scraped {len(works)} works, starting upsert to DB")
        # Upsert all works to DB
        for i, work in enumerate(works):
            await crud.upsert_work(work)
            if (i + 1) % 10 == 0:
                logger.info(f"[Task {task_id}] Upserted {i + 1}/{len(works)} works")

        progress_manager.update(task_id, 0.95, "保存数据", f"共 {len(works)} 个作品")

        # Update user's aweme_count - try to get uid from first work if available
        user_uid = works[0].uid if works and works[0].uid else None
        await crud.update_user_aweme_count(sec_user_id=sec_user_id, uid=user_uid)
        logger.info(f"[Task {task_id}] Updated user aweme_count to {len(works)}")

        # Refresh work info if requested (re-visit each work page for updated stats)
        refreshed_count = 0
        if refresh_info and works:
            logger.info(f"[Task {task_id}] Starting parallel work info refresh for {len(works)} works")
            progress_manager.update(task_id, 0.96, "刷新作品信息", f"准备并行刷新 {len(works)} 个作品")
            refreshed_count = await self._refresh_works_info_parallel(task_id, works)

        # Scrape comments if requested
        comments_count = 0
        if scrape_comments and works:
            logger.info(f"[Task {task_id}] Starting parallel comment scraping for {len(works)} works")
            progress_manager.update(task_id, 0.97, "采集评论", f"准备并行采集 {len(works)} 个作品的评论")
            comments_count = await self._scrape_comments_parallel(task_id, works)

        # Download media if requested
        download_count = 0
        if download_media and works:
            logger.info(f"[Task {task_id}] Starting parallel media download for {len(works)} works")
            progress_manager.update(task_id, 0.98, "下载媒体", f"准备并行下载 {len(works)} 个作品")
            download_count = await self._download_media_parallel(task_id, works)

        # Speech recognition if requested
        transcript_count = 0
        if speech_recognition and download_count > 0:
            logger.info(f"[Task {task_id}] Starting speech recognition for {len(works)} works")
            progress_manager.update(task_id, 0.98, "语音转写", f"准备对视频进行语音识别")

            for i, work in enumerate(works):
                # Check if task is cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled, stopping speech recognition")
                    break

                try:
                    # Find downloaded video file for this work
                    media_files = await crud.get_media_files(work.aweme_id)
                    video_path = None
                    for mf in media_files:
                        if mf.media_type == "video" and mf.download_status == "completed" and mf.local_path:
                            from pathlib import Path
                            if Path(mf.local_path).exists():
                                video_path = mf.local_path
                                break

                    if video_path:
                        progress_manager.update(
                            task_id,
                            0.98 + 0.01 * (i + 1) / len(works),
                            f"语音识别 {i+1}/{len(works)}",
                            work.aweme_id
                        )
                        text = await self.speech_recognizer.recognize(video_path)
                        if text:
                            await crud.update_work_transcript(work.aweme_id, text)
                            transcript_count += 1
                            logger.info(f"[Task {task_id}] Transcribed {len(text)} chars for {work.aweme_id}")
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to transcribe {work.aweme_id}: {e}")

        extra_info = []
        if refreshed_count > 0:
            extra_info.append(f"刷新 {refreshed_count} 个作品信息")
        if comments_count > 0:
            extra_info.append(f"{comments_count} 条评论")
        if download_count > 0:
            extra_info.append(f"下载 {download_count} 个媒体")
        if transcript_count > 0:
            extra_info.append(f"转写 {transcript_count} 个语音")

        progress_manager.update(task_id, 1.0, "完成", f"共采集 {len(works)} 个作品" + (", ".join(extra_info) if extra_info else ""))
        logger.info(f"[Task {task_id}] Completed: {len(works)} works upserted, {refreshed_count} refreshed, {comments_count} comments scraped, {download_count} media downloaded, {transcript_count} transcribed")
        return {
            "count": len(works),
            "refreshed_count": refreshed_count,
            "comments_count": comments_count,
            "media_downloaded": download_count,
            "transcript_count": transcript_count,
            "types": {
                "video": sum(1 for w in works if w.type == "video"),
                "note": sum(1 for w in works if w.type == "note"),
            },
        }

    async def _scrape_all(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape user profile and works with page reuse to minimize resource usage."""
        from backend.scraper.engine import engine

        # Acquire a single page for the entire task
        page = await engine.acquire_page(task_id)
        logger.info(f"[Task {task_id}] Acquired page for _scrape_all")

        try:
            # 1. Scrape profile with page reuse
            progress_manager.update(task_id, 0.05, "采集用户资料", sec_user_id)
            user = await self.user_scraper.scrape_profile(task_id, sec_user_id, page=page)

            # 2. Scrape works with the same page
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
                ),
                check_cancelled=lambda: self._check_cancelled(task_id),
                get_max_count=lambda: self._get_task_param(task_id, "max_count"),
                existing_page=page
            )

            # Upsert all works to DB
            for work in works:
                await crud.upsert_work(work)

            # Update user's aweme_count - try to get uid from first work if available
            user_uid = works[0].uid if works and works[0].uid else None
            await crud.update_user_aweme_count(sec_user_id=sec_user_id, uid=user_uid)
            logger.info(f"[Task {task_id}] Updated user aweme_count to {len(works)}")

            # Refresh work info if requested
            refreshed_count = 0
            if refresh_info and works:
                logger.info(f"[Task {task_id}] Starting parallel work info refresh for {len(works)} works")
                progress_manager.update(task_id, 0.61, "刷新作品信息", f"准备并行刷新 {len(works)} 个作品")
                refreshed_count = await self._refresh_works_info_parallel(task_id, works)

            # Download media if requested
            download_count = 0
            if params.get("download_media", False) and works:
                logger.info(f"[Task {task_id}] Starting parallel media download for {len(works)} works")
                progress_manager.update(task_id, 0.7, "下载媒体", f"准备并行下载 {len(works)} 个作品")
                download_count = await self._download_media_parallel(task_id, works)

            # Scrape comments if requested
            comments_count = 0
            if scrape_comments and works:
                logger.info(f"[Task {task_id}] Starting parallel comment scraping for {len(works)} works")
                progress_manager.update(task_id, 0.85, "采集评论", f"准备并行采集 {len(works)} 个作品的评论")
                comments_count = await self._scrape_comments_parallel(task_id, works)

            progress_manager.update(task_id, 1.0, "完成", "")
            return {
                "nickname": user.nickname if user else None,
                "works_count": len(works),
                "media_downloaded": download_count,
                "comments_count": comments_count,
                "refreshed_count": refreshed_count,
            }
        finally:
            # Release the page when task is complete
            await engine.release_page(task_id)
            logger.info(f"[Task {task_id}] Released page for _scrape_all")

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
        author_uid = params.get("uid", "")  # Prefer uid for work association
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
                author_info = aweme_detail.get("author", {})
                # Prefer uid from params, then from API response, then fallback
                work_uid = author_uid or author_info.get("uid", "") or ""
                work_sec_user_id = sec_user_id or author_info.get("sec_uid", "")
                work = Work(
                    aweme_id=aweme_id,
                    uid=work_uid,
                    sec_user_id=work_sec_user_id,
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

        # Check if already transcribed (prevent duplicate processing)
        work = await crud.get_work(aweme_id)
        if work and work.transcript:
            logger.info(f"[Task {task_id}] Work {aweme_id} already has transcript, skipping")
            progress_manager.update(task_id, 1.0, "完成", "已有语音转写")
            return {"aweme_id": aweme_id, "skipped": True, "reason": "already_transcribed"}

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
        """Scrape current user's liked videos with upsert (update if exists).
        Uses page reuse to minimize resource consumption.
        """
        from backend.scraper.engine import engine

        # Acquire a single page for the entire task
        page = await engine.acquire_page(task_id)
        logger.info(f"[Task {task_id}] Acquired page for _scrape_likes")

        try:
            max_pages = params.get("max_pages")
            max_count = params.get("max_count")
            collect_creators = params.get("collect_creators", False)
            download_media = params.get("download_media", False)
            scrape_comments = params.get("scrape_comments", False)
            speech_recognition = params.get("speech_recognition", False)
            progress_manager.update(task_id, 0.05, "开始采集喜欢的视频", "")

            works = await self.user_scraper.scrape_likes(
                task_id, sec_user_id, max_pages=max_pages, max_count=max_count,
                on_page=lambda page_num, total: progress_manager.update(
                    task_id,
                    min(0.1 + 0.6 * page_num / max(total, 1), 0.7),
                    f"采集第 {page_num} 页",
                    f"已获取喜欢的视频数据"
                ),
                check_cancelled=lambda: self._check_cancelled(task_id),
                get_max_count=lambda: self._get_task_param(task_id, "max_count"),
                existing_page=page
            )

            # Upsert all works (update if exists, insert if new)
            new_count = 0
            updated_count = 0
            processed_works = []
            for work in works:
                # Check if task was cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled during works upsert, stopping")
                    break

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

            # Check if task was cancelled before continuing
            if await self._check_cancelled(task_id):
                logger.info(f"[Task {task_id}] Task was cancelled, stopping further processing")
                return {"total": len(processed_works), "new": new_count, "updated": updated_count, "cancelled": True}

            # Download media if requested
            download_count = 0
            if download_media and processed_works:
                logger.info(f"[Task {task_id}] Starting parallel media download for {len(processed_works)} liked works")
                progress_manager.update(task_id, 0.75, "下载媒体", f"准备并行下载 {len(processed_works)} 个作品")
                download_count = await self._download_media_parallel(task_id, processed_works)

            # Scrape comments if requested
            comments_count = 0
            if scrape_comments and processed_works:
                logger.info(f"[Task {task_id}] Starting parallel comment scraping for {len(processed_works)} liked works")
                progress_manager.update(task_id, 0.86, "采集评论", f"准备并行采集 {len(processed_works)} 个作品的评论")
                comments_count = await self._scrape_comments_parallel(task_id, processed_works)

            # Collect creators if requested (reuse the same page)
            creators_collected = 0
            creators_skipped = 0
            if collect_creators and processed_works:
                # Collect unique author sec_user_ids
                author_ids = list(set(w.sec_user_id for w in processed_works))
                logger.info(f"[Task {task_id}] Found {len(author_ids)} unique creators from {len(processed_works)} works")

                # Filter out authors that already exist in database (recently updated)
                # Skip collection if user was updated within the last 7 days
                from datetime import datetime, timedelta
                recent_cutoff = datetime.now() - timedelta(days=7)

                authors_to_collect = []
                for author_id in author_ids:
                    existing_user = await crud.get_user(author_id)
                    if existing_user and existing_user.updated_at:
                        if existing_user.updated_at > recent_cutoff:
                            logger.info(f"[Task {task_id}] ⊘ Skipping {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                            creators_skipped += 1
                        else:
                            logger.info(f"[Task {task_id}] → Need update {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                            authors_to_collect.append(author_id)
                    else:
                        authors_to_collect.append(author_id)

                logger.info(f"[Task {task_id}] Will collect {len(authors_to_collect)} creators, skipped {creators_skipped} recent ones")

                if not authors_to_collect:
                    logger.info(f"[Task {task_id}] All creators already up-to-date, skipping collection")
                    creators_collected = 0
                else:
                    progress_manager.update(task_id, 0.91, "采集作者信息", f"准备并行采集 {len(authors_to_collect)} 个作者信息（已跳过 {creators_skipped} 个）")
                    creators_collected, _ = await self._collect_creators_parallel(task_id, authors_to_collect)

            # Speech recognition if requested
            transcript_count = 0
            if speech_recognition and download_count > 0:
                # Only process works that have downloaded video files
                logger.info(f"[Task {task_id}] Starting speech recognition for {len(processed_works)} works")
                progress_manager.update(task_id, 0.96, "语音转写", f"准备对视频进行语音识别")

                for i, work in enumerate(processed_works):
                    # Check if task is cancelled
                    if await self._check_cancelled(task_id):
                        logger.info(f"[Task {task_id}] Task was cancelled, stopping speech recognition")
                        break

                    try:
                        # Find downloaded video file for this work
                        media_files = await crud.get_media_files(work.aweme_id)
                        video_path = None
                        for mf in media_files:
                            if mf.media_type == "video" and mf.download_status == "completed" and mf.local_path:
                                from pathlib import Path
                                if Path(mf.local_path).exists():
                                    video_path = mf.local_path
                                    break

                        if video_path:
                            progress_manager.update(
                                task_id,
                                0.96 + 0.03 * (i + 1) / len(processed_works),
                                f"语音识别 {i+1}/{len(processed_works)}",
                                work.aweme_id
                            )
                            text = await self.speech_recognizer.recognize(video_path)
                            if text:
                                await crud.update_work_transcript(work.aweme_id, text)
                                transcript_count += 1
                                logger.info(f"[Task {task_id}] Transcribed {len(text)} chars for {work.aweme_id}")
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] Failed to transcribe {work.aweme_id}: {e}")

            extra_info = f"新增 {new_count} 个，更新 {updated_count} 个"
            if download_count > 0:
                extra_info += f"，下载 {download_count} 个媒体"
            if comments_count > 0:
                extra_info += f"，{comments_count} 条评论"
            if transcript_count > 0:
                extra_info += f"，转写 {transcript_count} 个语音"
            if creators_collected > 0:
                extra_info += f"，采集作者 {creators_collected} 个"

            # Log success
            logger.info(f"[Task {task_id}] ✅ scrape_likes COMPLETED: {len(processed_works)} works processed (new: {new_count}, updated: {updated_count})")
            progress_manager.update(task_id, 1.0, "完成", f"共处理 {len(processed_works)} 个作品")
            return {
                "total": len(processed_works),
                "new": new_count,
                "updated": updated_count,
                "media_downloaded": download_count,
                "comments_count": comments_count,
                "transcript_count": transcript_count,
                "creators_collected": creators_collected,
                "types": {
                    "video": sum(1 for w in processed_works if w.type == "video"),
                    "note": sum(1 for w in processed_works if w.type == "note"),
                },
            }
        finally:
            # Release the page when task is complete
            await engine.release_page(task_id)
            logger.info(f"[Task {task_id}] Released page for _scrape_likes")

    async def _scrape_favorites(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape current user's favorite videos with upsert (update if exists).
        Uses page reuse to minimize resource consumption.
        """
        from backend.scraper.engine import engine

        # Acquire a single page for the entire task
        page = await engine.acquire_page(task_id)
        logger.info(f"[Task {task_id}] Acquired page for _scrape_favorites")

        try:
            max_pages = params.get("max_pages")
            max_count = params.get("max_count")
            collect_creators = params.get("collect_creators", False)
            download_media = params.get("download_media", False)
            scrape_comments = params.get("scrape_comments", False)
            speech_recognition = params.get("speech_recognition", False)
            progress_manager.update(task_id, 0.05, "开始采集收藏的视频", "")

            works = await self.user_scraper.scrape_favorites(
                task_id, sec_user_id, max_pages=max_pages, max_count=max_count,
                on_page=lambda page_num, total: progress_manager.update(
                    task_id,
                    min(0.1 + 0.6 * page_num / max(total, 1), 0.7),
                    f"采集第 {page_num} 页",
                    f"已获取收藏的视频数据"
                ),
                check_cancelled=lambda: self._check_cancelled(task_id),
                existing_page=page
            )

            # Upsert all works (update if exists, insert if new)
            new_count = 0
            updated_count = 0
            processed_works = []
            for work in works:
                # Check if task was cancelled
                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task was cancelled during favorites upsert, stopping")
                    break

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

            # Check if task was cancelled before continuing
            if await self._check_cancelled(task_id):
                logger.info(f"[Task {task_id}] Task was cancelled, stopping further processing")
                return {"total": len(processed_works), "new": new_count, "updated": updated_count, "cancelled": True}

            # Download media if requested
            download_count = 0
            if download_media and processed_works:
                logger.info(f"[Task {task_id}] Starting parallel media download for {len(processed_works)} favorite works")
                progress_manager.update(task_id, 0.75, "下载媒体", f"准备并行下载 {len(processed_works)} 个作品")
                download_count = await self._download_media_parallel(task_id, processed_works)

            # Scrape comments if requested
            comments_count = 0
            if scrape_comments and processed_works:
                logger.info(f"[Task {task_id}] Starting parallel comment scraping for {len(processed_works)} favorite works")
                progress_manager.update(task_id, 0.86, "采集评论", f"准备并行采集 {len(processed_works)} 个作品的评论")
                comments_count = await self._scrape_comments_parallel(task_id, processed_works)

            # Collect creators if requested (reuse the same page)
            creators_collected = 0
            creators_skipped = 0
            if collect_creators and processed_works:
                # Collect unique author sec_user_ids
                author_ids = list(set(w.sec_user_id for w in processed_works))
                logger.info(f"[Task {task_id}] Found {len(author_ids)} unique creators from {len(processed_works)} works")

                # Filter out authors that already exist in database (recently updated)
                # Skip collection if user was updated within the last 7 days
                from datetime import datetime, timedelta
                recent_cutoff = datetime.now() - timedelta(days=7)

                authors_to_collect = []
                for author_id in author_ids:
                    existing_user = await crud.get_user(author_id)
                    if existing_user and existing_user.updated_at:
                        if existing_user.updated_at > recent_cutoff:
                            logger.info(f"[Task {task_id}] ⊘ Skipping {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                            creators_skipped += 1
                        else:
                            logger.info(f"[Task {task_id}] → Need update {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                            authors_to_collect.append(author_id)
                    else:
                        authors_to_collect.append(author_id)

                logger.info(f"[Task {task_id}] Will collect {len(authors_to_collect)} creators, skipped {creators_skipped} recent ones")

                if not authors_to_collect:
                    logger.info(f"[Task {task_id}] All creators already up-to-date, skipping collection")
                    creators_collected = 0
                else:
                    progress_manager.update(task_id, 0.91, "采集作者信息", f"准备并行采集 {len(authors_to_collect)} 个作者信息（已跳过 {creators_skipped} 个）")
                    creators_collected, _ = await self._collect_creators_parallel(task_id, authors_to_collect)

            # Speech recognition if requested
            transcript_count = 0
            if speech_recognition and download_count > 0:
                # Only process works that have downloaded video files
                logger.info(f"[Task {task_id}] Starting speech recognition for {len(processed_works)} works")
                progress_manager.update(task_id, 0.96, "语音转写", f"准备对视频进行语音识别")

                for i, work in enumerate(processed_works):
                    # Check if task is cancelled
                    if await self._check_cancelled(task_id):
                        logger.info(f"[Task {task_id}] Task was cancelled, stopping speech recognition")
                        break

                    try:
                        # Find downloaded video file for this work
                        media_files = await crud.get_media_files(work.aweme_id)
                        video_path = None
                        for mf in media_files:
                            if mf.media_type == "video" and mf.download_status == "completed" and mf.local_path:
                                from pathlib import Path
                                if Path(mf.local_path).exists():
                                    video_path = mf.local_path
                                    break

                        if video_path:
                            progress_manager.update(
                                task_id,
                                0.96 + 0.03 * (i + 1) / len(processed_works),
                                f"语音识别 {i+1}/{len(processed_works)}",
                                work.aweme_id
                            )
                            text = await self.speech_recognizer.recognize(video_path)
                            if text:
                                await crud.update_work_transcript(work.aweme_id, text)
                                transcript_count += 1
                                logger.info(f"[Task {task_id}] Transcribed {len(text)} chars for {work.aweme_id}")
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] Failed to transcribe {work.aweme_id}: {e}")

            extra_info = f"新增 {new_count} 个，更新 {updated_count} 个"
            if download_count > 0:
                extra_info += f"，下载 {download_count} 个媒体"
            if comments_count > 0:
                extra_info += f"，{comments_count} 条评论"
            if transcript_count > 0:
                extra_info += f"，转写 {transcript_count} 个语音"
            if creators_collected > 0:
                extra_info += f"，采集作者 {creators_collected} 个"

            # Log success
            logger.info(f"[Task {task_id}] ✅ scrape_favorites COMPLETED: {len(processed_works)} works processed (new: {new_count}, updated: {updated_count})")
            progress_manager.update(task_id, 1.0, "完成", f"共处理 {len(processed_works)} 个作品")
            return {
                "total": len(processed_works),
                "new": new_count,
                "updated": updated_count,
                "media_downloaded": download_count,
                "comments_count": comments_count,
                "transcript_count": transcript_count,
                "creators_collected": creators_collected,
                "types": {
                    "video": sum(1 for w in processed_works if w.type == "video"),
                    "note": sum(1 for w in processed_works if w.type == "note"),
                },
            }
        finally:
            # Release the page when task is complete
            await engine.release_page(task_id)
            logger.info(f"[Task {task_id}] Released page for _scrape_favorites")

    async def _scrape_following(self, task_id: int, sec_user_id: str, params: dict) -> dict:
        """Scrape user's following list with optional recursive collection.

        支持并行采集用户资料：
        1. 先递归收集所有关注列表中的用户 ID
        2. 然后使用子页面并行采集用户资料
        """
        from backend.scraper.engine import engine

        max_count = params.get("max_count")
        collect_profile = params.get("collect_profile", False)
        recursive = params.get("recursive", False)
        recursive_depth = params.get("recursive_depth", 1)

        logger.info(f"[Task {task_id}] Starting scrape_following for {sec_user_id}, max_count={max_count}, collect_profile={collect_profile}, recursive={recursive}, depth={recursive_depth}")
        progress_manager.update(task_id, 0.05, "开始采集关注列表", f"用户 {sec_user_id[:20]}...")

        # 使用 set 跟踪已处理的用户，避免重复
        processed_users = set()
        all_users_data = []

        # 在整个任务开始时获取页面, 复用于所有操作
        page = await engine.acquire_page(task_id)
        logger.debug(f"Acquired page for task {task_id}")

        try:
            # 用于跟踪是否达到限制
            reached_limit = False

            # 第一步：递归收集所有关注列表（不采集资料）
            async def collect_following_ids_recursive(target_id: str, current_depth: int):
                """递归收集关注列表中的用户 ID，不采集详细资料"""
                nonlocal reached_limit

                if reached_limit:
                    return

                if current_depth > recursive_depth:
                    return

                if target_id in processed_users:
                    return

                if await self._check_cancelled(task_id):
                    logger.info(f"[Task {task_id}] Task cancelled during following collection")
                    return

                processed_users.add(target_id)
                progress_manager.update(
                    task_id,
                    0.05 + 0.4 * (current_depth / max(recursive_depth, 1)),
                    f"采集关注列表 (深度 {current_depth}/{recursive_depth})",
                    f"已发现 {len(all_users_data)} 个用户" + (f" / {max_count}" if max_count else "")
                )

                # 计算剩余需要采集的数量
                remaining = max_count - len(all_users_data) if max_count else None

                # 获取关注列表，复用已有页面
                following_users = await self.user_scraper.scrape_following(
                    task_id, target_id, max_count=remaining,
                    on_page=None, check_cancelled=lambda: self._check_cancelled(task_id), existing_page=page
                )

                logger.info(f"[Task {task_id}] Found {len(following_users)} following for {target_id[:20]}... (total: {len(all_users_data)})")

                for user_info in following_users:
                    # 检查是否达到限制
                    if max_count and len(all_users_data) >= max_count:
                        logger.info(f"[Task {task_id}] Reached max_count limit: {len(all_users_data)} >= {max_count}")
                        reached_limit = True
                        break

                    following_id = user_info["sec_user_id"]
                    all_users_data.append(user_info)

                    # 递归收集（深度优先），但不要递归如果已达到限制
                    if recursive and current_depth < recursive_depth and not reached_limit:
                        await collect_following_ids_recursive(following_id, current_depth + 1)

            # 开始收集关注列表
            await collect_following_ids_recursive(sec_user_id, 1)

            logger.info(f"[Task {task_id}] Collected {len(all_users_data)} following users from {len(processed_users)} unique accounts")

            # 第二步：如果需要采集资料，使用子页面并行采集
            creators_collected = 0
            creators_skipped = 0
            if collect_profile and all_users_data:
                # 去重获取需要采集的用户 ID
                unique_author_ids = list(set(u["sec_user_id"] for u in all_users_data if u.get("sec_user_id")))
                logger.info(f"[Task {task_id}] Starting parallel profile collection for {len(unique_author_ids)} unique users")

                progress_manager.update(
                    task_id, 0.5,
                    "并行采集用户资料",
                    f"准备采集 {len(unique_author_ids)} 个用户"
                )

                creators_collected, creators_skipped = await self._collect_creators_parallel(task_id, unique_author_ids)

            progress_manager.update(task_id, 0.95, "保存数据", f"共采集 {len(all_users_data)} 个关注用户")
            progress_manager.update(
                task_id, 1.0, "完成",
                f"共采集 {len(all_users_data)} 个用户" + (f"，资料 {creators_collected} 个" if creators_collected > 0 else "")
            )

            logger.info(f"[Task {task_id}] Completed: {len(all_users_data)} users collected, {len(processed_users)} unique accounts, {creators_collected} profiles scraped")

            return {
                "total": len(all_users_data),
                "unique": len(processed_users),
                "collect_profile": collect_profile,
                "profiles_collected": creators_collected,
                "profiles_skipped": creators_skipped,
                "recursive": recursive,
                "depth": recursive_depth,
            }
        finally:
            # 在整个任务结束时释放页面
            try:
                await engine.release_page(task_id)
                logger.debug(f"Released page for task {task_id}")
            except Exception as e:
                logger.warning(f"Failed to release page for task {task_id}: {e}")

    async def _download_media_parallel(self, task_id: int, works: list, max_concurrent: int | None = None) -> int:
        """并行下载媒体（无需页面，使用 HTTP 请求）

        Args:
            task_id: 任务 ID
            works: 作品列表
            max_concurrent: 最大并发数，默认使用 settings.MAX_CONCURRENT_DOWNLOADS

        Returns:
            成功下载的数量
        """
        if max_concurrent is None:
            max_concurrent = settings.MAX_CONCURRENT_DOWNLOADS

        semaphore = asyncio.Semaphore(max_concurrent)
        download_count = 0

        async def download_one(work, index: int):
            nonlocal download_count
            async with semaphore:
                if await self._check_cancelled(task_id):
                    return 0
                progress_manager.update(
                    task_id, 0.75 + 0.2 * index / max(len(works), 1),
                    f"下载媒体 {index+1}/{len(works)}", work.aweme_id
                )
                try:
                    author_identifier = work.uid if work.uid else work.sec_user_id
                    await self.media_downloader.download_work_media(
                        work.aweme_id, author_identifier, work.extra_data
                    )
                    return 1
                except Exception as e:
                    logger.warning(f"Failed to download {work.aweme_id}: {e}")
                    return 0

        tasks = [download_one(w, i) for i, w in enumerate(works)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r == 1)

    async def _scrape_comments_parallel(self, task_id: int, works: list, max_concurrent: int | None = None) -> int:
        """并行采集评论（使用子页面）

        Args:
            task_id: 任务 ID
            works: 作品列表
            max_concurrent: 最大并发数，默认使用 settings.MAX_CONCURRENT_COMMENTS

        Returns:
            采集到的评论总数
        """
        from backend.scraper.engine import engine

        if max_concurrent is None:
            max_concurrent = settings.MAX_CONCURRENT_COMMENTS

        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_one(work, index: int):
            async with semaphore:
                if await self._check_cancelled(task_id):
                    return 0

                # 获取子页面
                subpage_id, page = await engine.acquire_subpage(task_id)
                try:
                    comments = await self.comment_scraper.scrape_comments(
                        work.aweme_id, max_pages=3, on_page=None, page=page
                    )
                    for comment in comments:
                        await crud.upsert_comment(comment)
                    logger.info(f"[Task {task_id}] Scraped {len(comments)} comments for {work.aweme_id}")
                    return len(comments)
                except Exception as e:
                    logger.warning(f"Failed to scrape comments for {work.aweme_id}: {e}")
                    return 0
                finally:
                    await engine.release_subpage(task_id, subpage_id)

        tasks = [scrape_one(w, i) for i, w in enumerate(works)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(r for r in results if isinstance(r, int))

    async def _refresh_works_info_parallel(self, task_id: int, works: list, max_concurrent: int | None = None) -> int:
        """并行刷新作品信息（使用子页面）

        Args:
            task_id: 任务 ID
            works: 作品列表
            max_concurrent: 最大并发数，默认使用 settings.MAX_CONCURRENT_REFRESH

        Returns:
            成功刷新的数量
        """
        from backend.scraper.engine import engine
        from backend.scraper.interceptor import ResponseInterceptor
        from backend.config import settings as config
        from backend.db.models import Work

        if max_concurrent is None:
            max_concurrent = settings.MAX_CONCURRENT_REFRESH

        semaphore = asyncio.Semaphore(max_concurrent)

        async def refresh_one(work, index: int):
            async with semaphore:
                if await self._check_cancelled(task_id):
                    return 0

                subpage_id, page = await engine.acquire_subpage(task_id)
                interceptor = ResponseInterceptor()

                try:
                    await interceptor.setup(page)
                    url = f"{config.DOUYIN_BASE_URL}/video/{work.aweme_id}"
                    ok = await engine.safe_goto(page, url)
                    if not ok:
                        return 0

                    data = await interceptor.wait_for("aweme/detail", timeout=15)
                    if not data:
                        data = await interceptor.wait_for("detail", timeout=5)

                    if data:
                        aweme_detail = data.get("aweme_detail", data)
                        stats = aweme_detail.get("statistics", {})
                        author_info = aweme_detail.get("author", {})
                        work_uid = work.uid or author_info.get("uid", "")
                        work_sec_user_id = work.sec_user_id or author_info.get("sec_uid", "")

                        updated_work = Work(
                            aweme_id=work.aweme_id,
                            uid=work_uid,
                            sec_user_id=work_sec_user_id,
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
                        await crud.upsert_work(updated_work)
                        return 1
                    return 0
                except Exception as e:
                    logger.warning(f"Failed to refresh {work.aweme_id}: {e}")
                    return 0
                finally:
                    await interceptor.teardown()
                    await engine.release_subpage(task_id, subpage_id)

        tasks = [refresh_one(w, i) for i, w in enumerate(works)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r == 1)

    async def _collect_creators_parallel(
        self,
        task_id: int,
        author_ids: list[str],
        max_concurrent: int | None = None
    ) -> tuple[int, int]:
        """并行采集作者信息（使用子页面）

        Args:
            task_id: 任务 ID
            author_ids: 作者 sec_user_id 列表
            max_concurrent: 最大并发数，默认使用 settings.MAX_CONCURRENT_DOWNLOADS

        Returns:
            (成功采集数量, 跳过数量)
        """
        from backend.scraper.engine import engine
        from datetime import datetime, timedelta

        if max_concurrent is None:
            max_concurrent = settings.MAX_CONCURRENT_DOWNLOADS

        # Filter out authors that already exist in database (recently updated)
        # Skip collection if user was updated within the last 7 days
        recent_cutoff = datetime.now() - timedelta(days=7)

        authors_to_collect = []
        creators_skipped = 0

        for author_id in author_ids:
            existing_user = await crud.get_user(author_id)
            if existing_user and existing_user.updated_at:
                if existing_user.updated_at > recent_cutoff:
                    logger.info(f"[Task {task_id}] ⊘ Skipping {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                    creators_skipped += 1
                else:
                    logger.info(f"[Task {task_id}] → Need update {author_id} (updated {existing_user.updated_at.strftime('%Y-%m-%d')})")
                    authors_to_collect.append(author_id)
            else:
                authors_to_collect.append(author_id)

        logger.info(f"[Task {task_id}] Will collect {len(authors_to_collect)} creators, skipped {creators_skipped} recent ones")

        if not authors_to_collect:
            logger.info(f"[Task {task_id}] All creators already up-to-date, skipping collection")
            return 0, creators_skipped

        semaphore = asyncio.Semaphore(max_concurrent)
        creators_collected = 0

        async def collect_one(author_id: str, index: int):
            nonlocal creators_collected
            async with semaphore:
                if await self._check_cancelled(task_id):
                    return 0

                progress_manager.update(
                    task_id,
                    0.91 + 0.04 * (index + 1) / len(authors_to_collect),
                    f"采集作者 {index+1}/{len(authors_to_collect)}",
                    author_id
                )

                # 获取子页面用于并行采集
                subpage_id, page = await engine.acquire_subpage(task_id)
                try:
                    logger.info(f"[Task {task_id}] Scraping profile for creator {index+1}/{len(authors_to_collect)}: {author_id}")
                    user = await self.user_scraper.scrape_profile(task_id, author_id, page=page)
                    if user:
                        await crud.upsert_user(user)
                        logger.info(f"[Task {task_id}] ✅ Collected creator: {user.nickname or author_id}")
                        return 1
                    else:
                        logger.warning(f"[Task {task_id}] ⚠️ No user data returned for {author_id}")
                        return 0
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Failed to collect creator {author_id}: {e}")
                    return 0
                finally:
                    await engine.release_subpage(task_id, subpage_id)

        tasks = [collect_one(aid, i) for i, aid in enumerate(authors_to_collect)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        creators_collected = sum(1 for r in results if r == 1)

        return creators_collected, creators_skipped
