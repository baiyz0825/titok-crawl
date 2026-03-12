from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import crud
from backend.queue.scheduler import scheduler

router = APIRouter(prefix="/api/works", tags=["works"])


class BatchDeleteWorksRequest(BaseModel):
    aweme_ids: list[str]


@router.get("")
async def list_works(
    sec_user_id: str | None = None,
    type: str | None = None,
    page: int = 1,
    size: int = 20,
    sort_by: str = "publish_time",
    sort_order: str = "DESC",
):
    """List works with optional filters and sorting."""
    works = await crud.get_works(
        sec_user_id=sec_user_id, work_type=type, page=page, size=size,
        sort_by=sort_by, sort_order=sort_order,
    )
    total = await crud.count_works(sec_user_id=sec_user_id, work_type=type)
    return {
        "items": [w.model_dump() for w in works],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/batch-delete")
async def delete_works_batch(req: BatchDeleteWorksRequest):
    await crud.delete_works_batch(req.aweme_ids)
    return {"deleted": len(req.aweme_ids)}


@router.get("/{aweme_id}")
async def get_work(aweme_id: str):
    """Get work detail with media files and comments."""
    work = await crud.get_work(aweme_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    media = await crud.get_media_files(aweme_id)
    comments = await crud.get_comments(aweme_id, page=1, size=50)
    comment_total = await crud.count_comments(aweme_id)

    # Scrape status
    has_comments = comment_total > 0
    has_media = len(media) > 0
    media_downloaded = any(m.download_status == 'completed' for m in media)

    return {
        **work.model_dump(),
        "media_files": [m.model_dump() for m in media],
        "comments": [c.model_dump() for c in comments],
        "comment_total": comment_total,
        "scrape_status": {
            "profile_scraped": True,
            "comments_scraped": has_comments,
            "comments_count": comment_total,
            "media_downloaded": media_downloaded,
            "media_count": len(media),
            "last_updated": work.updated_at.isoformat() if work.updated_at else None,
        }
    }


@router.delete("/{aweme_id}")
async def delete_work(aweme_id: str):
    await crud.delete_work(aweme_id)
    return {"deleted": True}


@router.get("/{aweme_id}/comments")
async def get_work_comments(aweme_id: str, page: int = 1, size: int = 50):
    """Get comments for a work."""
    comments = await crud.get_comments(aweme_id, page=page, size=size)
    total = await crud.count_comments(aweme_id)
    return {
        "items": [c.model_dump() for c in comments],
        "total": total,
        "page": page,
        "size": size,
    }


class RescrapeWorkRequest(BaseModel):
    sync_types: list[str] = ["comments"]  # "comments", "media", "work_info"


@router.post("/{aweme_id}/rescrape")
async def rescrape_work(aweme_id: str, req: RescrapeWorkRequest | None = None):
    """Re-scrape a specific work's data. Supports multiple sync_types at once."""
    sync_types = req.sync_types if req else ["comments"]

    # Get work info for media download params
    work = await crud.get_work(aweme_id)
    task_ids = []

    for sync_type in sync_types:
        if sync_type == "media":
            kwargs = {}
            if work:
                kwargs["sec_user_id"] = work.sec_user_id
                kwargs["extra_data"] = work.extra_data
            task_id = await scheduler.submit(
                task_type="media_download", target=aweme_id, **kwargs,
            )
            task_ids.append(task_id)
        elif sync_type == "work_info":
            kwargs = {}
            if work:
                kwargs["sec_user_id"] = work.sec_user_id
            task_id = await scheduler.submit(
                task_type="work_info", target=aweme_id, **kwargs,
            )
            task_ids.append(task_id)
        elif sync_type == "comments":
            task_id = await scheduler.submit(task_type="comments", target=aweme_id)
            task_ids.append(task_id)

    return {"task_ids": task_ids}
