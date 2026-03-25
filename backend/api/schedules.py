from fastapi import APIRouter, Query, HTTPException

from backend.db import crud

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("")
async def list_schedules(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Number of items per page (max 100)"),
    status: str | None = Query(None, description="Filter by task status"),
):
    """List scheduled tasks with pagination.

    Returns paginated list of scheduled tasks sorted by next_run_at.
    """
    from backend.db.models import Task

    tasks = await crud.get_scheduled_tasks(page=page, size=size, status=status)
    total = await crud.count_scheduled_tasks(status=status)
    return {
        "items": [t.model_dump() for t in tasks],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("")
async def create_schedule(
    sec_user_id: str,
    sync_type: str = Query("all", description="Type of sync: 'all' or specific data type"),
    interval_minutes: int = Query(1440, ge=1, description="Interval in minutes (default 1440 = daily)"),
):
    """Create a new scheduled task.

    Creates a scheduled task that will run periodically at the specified interval.
    """
    from backend.queue.scheduler import scheduler

    # Determine task type based on sync_type
    task_type = "user_all" if sync_type == "all" else f"user_{sync_type}"

    try:
        task_id = await scheduler.submit(
            task_type=task_type,
            target=sec_user_id,
            is_scheduled=True,
            schedule_interval=interval_minutes,
        )
        return {"id": task_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create schedule: {str(e)}")


@router.put("/{task_id}")
async def update_schedule(
    task_id: int,
    status: str | None = Query(None, description="New task status"),
):
    """Update a scheduled task.

    Allows updating task status (e.g., to pause/resume).
    """
    from backend.db import crud as db_crud

    # Check if task exists
    task = await db_crud.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.is_scheduled:
        raise HTTPException(status_code=400, detail="Task is not a scheduled task")

    updates = {}
    if status is not None:
        # Validate status
        valid_statuses = ["pending", "running", "paused", "completed", "failed", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        updates["status"] = status

    if not updates:
        return {"status": "no changes"}

    await db_crud.update_task(task_id, **updates)
    return {"status": "updated"}


@router.delete("/{task_id}")
async def delete_schedule(task_id: int):
    """Delete a scheduled task.

    Permanently removes the scheduled task from the database.
    """
    from backend.db import crud as db_crud

    # Check if task exists
    task = await db_crud.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if it's a scheduled task
    if not task.is_scheduled:
        raise HTTPException(status_code=400, detail="Task is not a scheduled task")

    await db_crud.delete_task(task_id)
    return {"status": "deleted"}
