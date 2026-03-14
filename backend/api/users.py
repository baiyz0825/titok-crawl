from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import crud
from backend.queue.scheduler import scheduler

router = APIRouter(prefix="/api/users", tags=["users"])


class BatchDeleteRequest(BaseModel):
    sec_user_ids: list[str]
    cascade: bool = False


class ScrapeUserRequest(BaseModel):
    identifier: str  # can be sec_user_id, douyin_id, or nickname
    sync_type: str = "all"  # "all", "profile", "works"


class RescrapeRequest(BaseModel):
    sync_type: str = "all"  # "all", "profile", "works", "comments"


@router.post("/scrape")
async def scrape_user(req: ScrapeUserRequest):
    """Submit a user scraping task. Identifier can be sec_user_id or search keyword."""
    identifier = req.identifier.strip()

    # Determine if it looks like a sec_user_id (starts with MS4 or is very long)
    if identifier.startswith("MS4") or len(identifier) > 30:
        sec_user_id = identifier
    else:
        # Try to find locally first
        local_users = await crud.search_users_local(identifier, limit=1)
        if local_users:
            sec_user_id = local_users[0].sec_user_id
        else:
            # Need to search on Douyin - create a search task and return
            from backend.scraper.search_scraper import SearchScraper
            searcher = SearchScraper()
            results = await searcher.search(identifier, search_type="user")
            if results:
                sec_user_id = results[0]["sec_user_id"]
            else:
                raise HTTPException(status_code=404, detail="未找到该用户，请输入完整的 sec_user_id")

    type_map = {"all": "user_all", "profile": "user_profile", "works": "user_works"}
    task_type = type_map.get(req.sync_type, "user_all")
    task_id = await scheduler.submit(task_type=task_type, target=sec_user_id)
    return {"task_id": task_id, "task_type": task_type, "sec_user_id": sec_user_id}


@router.delete("/batch")
async def delete_users_batch(req: BatchDeleteRequest):
    await crud.delete_users_batch(req.sec_user_ids, cascade=req.cascade)
    return {"deleted": len(req.sec_user_ids)}


@router.get("")
async def list_users(
    page: int = 1,
    size: int = 20,
    keyword: str = "",
    sort_by: str = "updated_at",
    sort_order: str = "DESC"
):
    """List scraped users with pagination, search, and sorting."""
    if keyword:
        users = await crud.search_users_local(keyword, limit=size)
        total = len(users)
    else:
        users = await crud.get_users(page=page, size=size, sort_by=sort_by, sort_order=sort_order)
        total = await crud.count_users()
    return {
        "items": [u.model_dump() for u in users],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/delete-preview")
async def get_delete_preview(sec_user_ids: list[str] = Query(...), cascade: bool = False):
    """Get preview of what will be deleted for confirmation."""
    preview = await crud.get_delete_preview(sec_user_ids, cascade)
    return preview


@router.delete("/{sec_user_id}")
async def delete_user(sec_user_id: str, cascade: bool = False):
    await crud.delete_user(sec_user_id, cascade=cascade)
    return {"deleted": True}


@router.get("/{sec_user_id}")
async def get_user(sec_user_id: str):
    """Get user detail with scrape status."""
    user = await crud.get_user(sec_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Get scrape status
    works_count = await crud.count_works(sec_user_id=sec_user_id)
    comments_count = await crud.count_user_comments(sec_user_id)
    media_count = await crud.count_user_media(sec_user_id)

    return {
        **user.model_dump(),
        "scrape_status": {
            "works_count": works_count,
            "comments_count": comments_count,
            "media_count": media_count,
            "profile_scraped": True,
            "profile_updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    }


@router.post("/{sec_user_id}/rescrape")
async def rescrape_user(sec_user_id: str, req: RescrapeRequest | None = None):
    sync_type = req.sync_type if req else "all"
    type_map = {"all": "user_all", "profile": "user_profile", "works": "user_works", "comments": "comments"}
    task_type = type_map.get(sync_type, "user_all")
    target = sec_user_id
    task_id = await scheduler.submit(task_type=task_type, target=target)
    return {"task_id": task_id}
