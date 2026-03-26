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
        # Extract scheduled task parameters
        is_scheduled = params.pop("is_scheduled", False)
        schedule_interval = params.pop("schedule_interval", None)
        next_run_at = params.pop("next_run_at", None)
        priority = params.pop("priority", 0) if "priority" in params else 0

        task = Task(
            task_type=task_type,
            target=target,
            params=json.dumps(params, ensure_ascii=False) if params else None,
            priority=priority,
            is_scheduled=is_scheduled,
            schedule_interval=schedule_interval,
            next_run_at=datetime.fromisoformat(next_run_at) if next_run_at else None,
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
        """Main scheduler loop - supports concurrent task execution."""
        # Semaphore to control concurrent task execution
        max_concurrent = getattr(settings, 'MAX_CONCURRENT_TASKS', 3)
        self._task_semaphore = asyncio.Semaphore(max_concurrent)
        self._running_tasks: dict[int, asyncio.Task] = {}

        logger.info(f"Scheduler started with max {max_concurrent} concurrent tasks")

        while self._running:
            try:
                # Check if we can start more tasks
                if len(self._running_tasks) >= max_concurrent:
                    # Wait for at least one task to complete
                    await asyncio.wait(
                        list(self._running_tasks.values()),
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    # Clean up completed tasks
                    completed = [tid for tid, t in self._running_tasks.items() if t.done()]
                    for tid in completed:
                        del self._running_tasks[tid]
                    continue

                # Get next pending task
                task = await crud.get_next_pending_task()
                if task is None:
                    if self._running_tasks:
                        # Wait a bit for running tasks
                        await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(2)
                    continue

                # Start task execution with semaphore
                task_coro = self._execute_task_with_semaphore(task)
                task_future = asyncio.create_task(task_coro)
                self._running_tasks[task.id] = task_future
                logger.info(f"Started task #{task.id} ({len(self._running_tasks)}/{max_concurrent} concurrent)")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)

        # Wait for all running tasks to complete
        if self._running_tasks:
            logger.info(f"Waiting for {len(self._running_tasks)} running tasks to complete...")
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

    async def _execute_task_with_semaphore(self, task):
        """Execute a single task with semaphore control."""
        async with self._task_semaphore:
            self._current_task_id = task.id

            # Task is already marked as 'running' by get_next_pending_task()
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

    async def _schedule_check_loop(self):
        """Check for due scheduled tasks every 60 seconds."""
        while self._running:
            try:
                due_tasks = await crud.get_due_scheduled_tasks()
                for task in due_tasks:
                    # For scheduled tasks, we need to execute them and update next_run_at
                    # Reset the task to pending so it can be picked up by the main scheduler loop
                    if task.status == 'completed':
                        await crud.update_task(task.id, status='pending')
                        logger.info(f"Scheduled task #{task.id} reactivated: {task.task_type} -> {task.target}")

                    # Update next_run_at for this scheduled task
                    if task.schedule_interval:
                        await crud.update_scheduled_task_next_run(task.id, task.schedule_interval)
                        logger.info(f"Updated next_run_at for scheduled task #{task.id}")

                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Schedule check error: {e}")
                await asyncio.sleep(60)


# Global singleton
scheduler = TaskScheduler()
