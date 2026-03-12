import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

from backend.config import settings
from backend.db import crud
from backend.db.models import Task
from backend.queue.worker import TaskWorker

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Async task scheduler backed by SQLite."""

    def __init__(self):
        self.worker = TaskWorker()
        self._running = False
        self._task: asyncio.Task | None = None
        self._schedule_task: asyncio.Task | None = None
        self._current_task_id: int | None = None

    async def start(self):
        """Start the scheduler loop."""
        await crud.reset_running_tasks()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._schedule_task = asyncio.create_task(self._schedule_check_loop())
        logger.info("Task scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for t in (self._task, self._schedule_task):
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        logger.info("Task scheduler stopped")

    async def submit(self, task_type: str, target: str, **params) -> int:
        """Submit a new task. Returns task_id."""
        task = Task(
            task_type=task_type,
            target=target,
            params=json.dumps(params, ensure_ascii=False) if params else None,
            priority=params.pop("priority", 0) if "priority" in params else 0,
        )
        task_id = await crud.create_task(task)
        logger.info(f"Task submitted: #{task_id} {task_type} -> {target}")
        return task_id

    async def cancel(self, task_id: int) -> bool:
        """Cancel a pending or running task."""
        task = await crud.get_task(task_id)
        if task is None:
            return False
        if task.status in ("pending", "running"):
            await crud.update_task(task_id, status="cancelled")
            logger.info(f"Task #{task_id} cancelled")
            return True
        return False

    async def retry(self, task_id: int) -> bool:
        """Retry a failed task."""
        task = await crud.get_task(task_id)
        if task is None:
            return False
        if task.status == "failed":
            await crud.update_task(
                task_id, status="pending", retry_count=0, error_message=None
            )
            logger.info(f"Task #{task_id} queued for retry")
            return True
        return False

    async def pause(self, task_id: int) -> bool:
        """Pause a running task."""
        task = await crud.get_task(task_id)
        if task is None:
            return False
        if task.status == "running":
            await crud.update_task(task_id, status="paused")
            logger.info(f"Task #{task_id} paused")
            return True
        return False

    async def resume_task(self, task_id: int) -> bool:
        """Resume a paused task."""
        task = await crud.get_task(task_id)
        if task is None:
            return False
        if task.status == "paused":
            await crud.update_task(task_id, status="pending")
            logger.info(f"Task #{task_id} resumed")
            return True
        return False

    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                task = await crud.get_next_pending_task()
                if task is None:
                    await asyncio.sleep(2)
                    continue

                self._current_task_id = task.id

                # Mark as running
                now = datetime.now().isoformat()
                await crud.update_task(task.id, status="running", started_at=now)
                logger.info(f"Executing task #{task.id}: {task.task_type} -> {task.target}")

                try:
                    result = await self.worker.execute(
                        task.id, task.task_type, task.target, task.params
                    )
                    now = datetime.now().isoformat()
                    await crud.update_task(
                        task.id,
                        status="completed",
                        progress=1.0,
                        result=json.dumps(result, ensure_ascii=False),
                        completed_at=now,
                    )
                    logger.info(f"Task #{task.id} completed")

                except Exception as e:
                    logger.error(f"Task #{task.id} failed: {e}")
                    retry_count = (task.retry_count or 0) + 1
                    if retry_count < task.max_retries:
                        await crud.update_task(
                            task.id,
                            status="pending",
                            retry_count=retry_count,
                            error_message=str(e),
                        )
                        logger.info(f"Task #{task.id} will retry ({retry_count}/{task.max_retries})")
                    else:
                        await crud.update_task(
                            task.id,
                            status="failed",
                            retry_count=retry_count,
                            error_message=str(e),
                        )

                self._current_task_id = None

                # Random delay between tasks
                delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)

    async def _schedule_check_loop(self):
        """Check for due scheduled tasks every 60 seconds."""
        while self._running:
            try:
                due = await crud.get_due_schedules()
                for schedule in due:
                    # Create task based on sync_type
                    task_type_map = {
                        "profile": "user_profile",
                        "works": "user_works",
                        "all": "user_all",
                        "likes": "user_likes",
                        "favorites": "user_favorites",
                    }
                    task_type = task_type_map.get(schedule.sync_type, "user_all")
                    await self.submit(task_type, schedule.sec_user_id)
                    logger.info(f"Scheduled task created: {task_type} for {schedule.nickname or schedule.sec_user_id}")

                    # Update next_run_at
                    next_run = (datetime.now() + timedelta(minutes=schedule.interval_minutes)).isoformat()
                    await crud.update_schedule(
                        schedule.id,
                        last_run_at=datetime.now().isoformat(),
                        next_run_at=next_run,
                    )

                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schedule check error: {e}")
                await asyncio.sleep(60)


# Global singleton
scheduler = TaskScheduler()
