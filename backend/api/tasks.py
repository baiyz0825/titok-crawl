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


@router.get("")
async def list_tasks(status: str | None = None, page: int = 1, size: int = 20):
    """List tasks with optional status filter."""
    tasks = await crud.get_tasks(status=status, page=page, size=size)
    total = await crud.count_tasks(status=status)
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


@router.post("/batch-delete")
async def delete_tasks_batch(req: BatchDeleteTasksRequest):
    await crud.delete_tasks_batch(req.task_ids)
    return {"deleted": len(req.task_ids)}


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
