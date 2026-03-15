import asyncio
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from backend.db import crud
from backend.queue.scheduler import scheduler
from backend.queue.progress import progress_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class BatchDeleteTasksRequest(BaseModel):
    task_ids: list[int]


class UpdatePriorityRequest(BaseModel):
    priority: int


class CreateTaskRequest(BaseModel):
    task_type: str
    target: str
    max_pages: int | None = None
    max_count: int | None = None
    download_media: bool = False
    scrape_comments: bool = False
    refresh_info: bool = False
    collect_profile: bool = False
    collect_creators: bool = False
    recursive: bool = False
    recursive_depth: int = 1
    priority: int = 0
    is_scheduled: bool = False
    schedule_interval: int | None = None
    next_run_at: str | None = None  # ISO format timestamp


@router.get("")
async def list_tasks(
    status: str | None = None,
    task_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    size: int = 20
):
    """List tasks with optional filters."""
    tasks = await crud.get_tasks(
        status=status,
        task_type=task_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        size=size
    )
    total = await crud.count_tasks(
        status=status,
        task_type=task_type,
        start_date=start_date,
        end_date=end_date
    )
    return {
        "items": [t.model_dump() for t in tasks],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/progress/stream")
async def progress_stream(task_id: int | None = None):
    """SSE endpoint for task progress updates."""
    q = progress_manager.subscribe(task_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            progress_manager.unsubscribe(q, task_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/stats")
async def get_tasks_stats(
    start_date: str | None = None,
    end_date: str | None = None
):
    """Get task statistics for a date range."""
    # Get all tasks in the date range
    tasks = await crud.get_tasks(
        status=None,
        task_type=None,
        start_date=start_date,
        end_date=end_date,
        page=1,
        size=99999  # Get all tasks
    )

    # Calculate statistics
    total = len(tasks)
    by_status = {}
    for task in tasks:
        status = task.status
        by_status[status] = by_status.get(status, 0) + 1

    completed = by_status.get('completed', 0)
    success_rate = (completed / total * 100) if total > 0 else 0

    return {
        "total": total,
        "by_status": by_status,
        "success_rate": round(success_rate, 1)
    }


@router.post("")
async def create_task(req: CreateTaskRequest):
    """Create a new task."""
    params = {
        "max_pages": req.max_pages,
        "max_count": req.max_count,
        "download_media": req.download_media,
        "scrape_comments": req.scrape_comments,
        "refresh_info": req.refresh_info,
        "collect_profile": req.collect_profile,
        "collect_creators": req.collect_creators,
        "recursive": req.recursive,
        "recursive_depth": req.recursive_depth,
        "priority": req.priority,
        "is_scheduled": req.is_scheduled,
        "schedule_interval": req.schedule_interval,
        "next_run_at": req.next_run_at
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    task_id = await scheduler.submit(
        task_type=req.task_type,
        target=req.target,
        **params
    )
    return {"task_id": task_id, "status": "pending"}


@router.post("/batch-delete")
async def delete_tasks_batch(req: BatchDeleteTasksRequest):
    await crud.delete_tasks_batch(req.task_ids)
    return {"deleted": len(req.task_ids)}


class BatchTaskIdsRequest(BaseModel):
    task_ids: list[int]


@router.post("/batch-pause")
async def pause_tasks_batch(req: BatchTaskIdsRequest):
    """Pause multiple running tasks."""
    paused = 0
    for task_id in req.task_ids:
        task = await crud.get_task(task_id)
        if task and task.status == "running":
            await crud.update_task(task_id, status="paused")
            paused += 1
    return {"paused": paused}


@router.post("/batch-resume")
async def resume_tasks_batch(req: BatchTaskIdsRequest):
    """Resume multiple paused tasks."""
    resumed = 0
    for task_id in req.task_ids:
        task = await crud.get_task(task_id)
        if task and task.status == "paused":
            await crud.update_task(task_id, status="pending")
            resumed += 1
    # Trigger scheduler to pick up resumed tasks
    return {"resumed": resumed}


@router.post("/batch-retry")
async def retry_tasks_batch(req: BatchTaskIdsRequest):
    """Retry multiple failed tasks."""
    retried = 0
    for task_id in req.task_ids:
        task = await crud.get_task(task_id)
        if task and task.status == "failed":
            await crud.update_task(
                task_id,
                status="pending",
                retry_count=0,
                error_message=None
            )
            retried += 1
    return {"retried": retried}


@router.post("/batch-cancel")
async def cancel_tasks_batch(req: BatchTaskIdsRequest):
    """Cancel multiple pending or running tasks."""
    cancelled = 0
    for task_id in req.task_ids:
        success = await scheduler.cancel(task_id)
        if success:
            cancelled += 1
    return {"cancelled": cancelled}


@router.get("/{task_id}")
async def get_task(task_id: int):
    """Get task detail."""
    task = await crud.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    data = task.model_dump()
    # Attach latest progress info if available
    latest = progress_manager.get_latest(task_id)
    if latest:
        data["live_progress"] = latest
    return data


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: int):
    """Cancel a pending or running task."""
    success = await scheduler.cancel(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel this task")
    return {"status": "cancelled"}


@router.post("/{task_id}/retry")
async def retry_task(task_id: int):
    """Retry a failed task."""
    success = await scheduler.retry(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot retry this task")
    return {"status": "retrying"}


@router.post("/{task_id}/priority")
async def update_task_priority(task_id: int, req: UpdatePriorityRequest):
    task = await crud.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending tasks can change priority")
    await crud.update_task(task_id, priority=req.priority)
    return {"status": "updated"}


@router.post("/{task_id}/pause")
async def pause_task(task_id: int):
    """Pause a running task (mark as paused)."""
    success = await scheduler.pause(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause this task")
    return {"status": "paused"}


@router.post("/{task_id}/resume")
async def resume_task(task_id: int):
    """Resume a paused task."""
    success = await scheduler.resume_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resume this task")
    return {"status": "resumed"}
