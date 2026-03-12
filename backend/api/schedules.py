from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import crud
from backend.db.models import Schedule

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    sec_user_id: str
    nickname: str | None = None
    sync_type: str = "all"
    interval_minutes: int = 1440


class ScheduleUpdate(BaseModel):
    sync_type: str | None = None
    interval_minutes: int | None = None
    enabled: bool | None = None


@router.get("")
async def list_schedules():
    """List all scheduled sync tasks."""
    schedules = await crud.get_schedules()
    return {"items": [s.model_dump() for s in schedules], "total": len(schedules)}


@router.post("")
async def create_schedule(req: ScheduleCreate):
    """Create a new scheduled sync task."""
    schedule = Schedule(
        sec_user_id=req.sec_user_id,
        nickname=req.nickname,
        sync_type=req.sync_type,
        interval_minutes=req.interval_minutes,
    )
    schedule_id = await crud.create_schedule(schedule)
    return {"id": schedule_id, "status": "created"}


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: int, req: ScheduleUpdate):
    """Update a scheduled sync task."""
    existing = await crud.get_schedule(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if updates:
        await crud.update_schedule(schedule_id, **updates)
    return {"status": "updated"}


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: int):
    """Delete a scheduled sync task."""
    existing = await crud.get_schedule(schedule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await crud.delete_schedule(schedule_id)
    return {"status": "deleted"}
