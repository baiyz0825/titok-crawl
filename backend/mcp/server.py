import json
import logging

from mcp.server.fastmcp import FastMCP

from backend.db import crud
from backend.analysis.analyzer import analyzer
from backend.config import settings

logger = logging.getLogger(__name__)

mcp_server = FastMCP("douyin-scraper", host="0.0.0.0", port=settings.MCP_PORT)


@mcp_server.tool()
async def scrape_user(identifier: str, sync_type: str = "all") -> str:
    """Scrape a Douyin user's data. Creates a background task.

    Args:
        identifier: User identifier (sec_user_id, douyin_id, or nickname)
        sync_type: Type of data to scrape - "all", "profile", or "works" (default: "all")
    """
    identifier = identifier.strip()

    # Determine if it looks like a sec_user_id (starts with MS4 or is very long)
    if identifier.startswith("MS4") or len(identifier) > 30:
        sec_user_id = identifier
    else:
        # Try to find locally first
        local_users = await crud.search_users_local(identifier, limit=1)
        if local_users:
            sec_user_id = local_users[0].sec_user_id
        else:
            return json.dumps({"error": f"User '{identifier}' not found in local database. Please provide full sec_user_id."})

    type_map = {"all": "user_all", "profile": "user_profile", "works": "user_works"}
    task_type = type_map.get(sync_type, "user_all")
    task = await crud.create_task(
        task_type=task_type,
        params={"sec_user_id": sec_user_id},
    )
    return json.dumps({"task_id": task.id, "status": "pending", "task_type": task_type, "sec_user_id": sec_user_id})


@mcp_server.tool()
async def scrape_user_works(sec_user_id: str, max_pages: int = 5) -> str:
    """Scrape all works (videos/notes) from a Douyin user. Creates a background task.

    Args:
        sec_user_id: The user's sec_user_id
        max_pages: Maximum pages to scrape (default 5)
    """
    task = await crud.create_task(
        task_type="user_works",
        params={"sec_user_id": sec_user_id, "max_pages": max_pages},
    )
    return json.dumps({"task_id": task.id, "status": "pending"})


@mcp_server.tool()
async def search_users(keyword: str) -> str:
    """Search for Douyin users by keyword. Creates a background task.

    Args:
        keyword: Search keyword
    """
    task = await crud.create_task(
        task_type="search",
        params={"keyword": keyword, "type": "user"},
    )
    return json.dumps({"task_id": task.id, "status": "pending"})


@mcp_server.tool()
async def lookup_user(keyword: str) -> str:
    """Look up a Douyin user by nickname or douyin_id from local database.
    Returns matching users with their sec_user_id.

    Args:
        keyword: User nickname or douyin_id to search for
    """
    users = await crud.search_users_local(keyword, limit=10)
    if not users:
        return json.dumps({"matches": [], "message": "No matching users found in local database"}, ensure_ascii=False)
    return json.dumps({
        "matches": [
            {
                "nickname": u.nickname,
                "sec_user_id": u.sec_user_id,
                "douyin_id": u.douyin_id,
                "uid": u.uid,
                "avatar_url": u.avatar_url,
                "follower_count": u.follower_count,
                "aweme_count": u.aweme_count,
            }
            for u in users
        ],
        "total": len(users),
    }, ensure_ascii=False, default=str)


@mcp_server.tool()
async def get_user_info(user_id: str) -> str:
    """Get stored user profile information from database.

    Args:
        user_id: User's uid or sec_user_id (uid preferred)
    """
    # Try uid first (more reliable), then sec_user_id
    user = await crud.get_user_by_uid(user_id)
    if user is None:
        user = await crud.get_user(user_id)
    if not user:
        return json.dumps({"error": "User not found in database"})

    # Get scrape status
    works_count = await crud.count_works(sec_user_id=user.sec_user_id, uid=user.uid)
    comments_count = await crud.count_user_comments(sec_user_id=user.sec_user_id, uid=user.uid)
    media_count = await crud.count_user_media(sec_user_id=user.sec_user_id, uid=user.uid)

    return json.dumps({
        **user.model_dump(),
        "scrape_status": {
            "works_count": works_count,
            "comments_count": comments_count,
            "media_count": media_count,
            "profile_scraped": True,
            "profile_updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    }, ensure_ascii=False, default=str)


@mcp_server.tool()
async def get_works(
    sec_user_id: str | None = None,
    uid: str | None = None,
    type: str | None = None,
    page: int = 1,
    size: int = 20,
    sort_by: str = "publish_time",
    sort_order: str = "DESC",
    start_date: str | None = None,
    end_date: str | None = None,
    has_comments: bool | None = None,
    has_media: bool | None = None,
    has_transcript: bool | None = None
) -> str:
    """Get stored works from database with optional filters.

    Args:
        sec_user_id: Filter by user's sec_user_id (fallback, optional)
        uid: Filter by user's uid (preferred, optional)
        type: Filter by work type: 'video' or 'note' (optional)
        page: Page number (default 1)
        size: Page size (default 20)
        sort_by: Sort field (default "publish_time")
        sort_order: Sort order "ASC" or "DESC" (default "DESC")
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        has_comments: Filter works with comments (optional)
        has_media: Filter works with media files (optional)
        has_transcript: Filter works with transcript (optional)
    """
    filter_kwargs = dict(
        sec_user_id=sec_user_id,
        uid=uid,
        work_type=type,
        start_date=start_date,
        end_date=end_date,
        has_comments=has_comments,
        has_media=has_media,
        has_transcript=has_transcript,
    )
    works = await crud.get_works(
        **filter_kwargs,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = await crud.count_works(**filter_kwargs)
    return json.dumps(
        {"items": [w.model_dump() for w in works], "total": total, "page": page, "size": size},
        ensure_ascii=False,
        default=str
    )


@mcp_server.tool()
async def get_task_status(task_id: int) -> str:
    """Get the status of a scraping task.

    Args:
        task_id: The task ID
    """
    task = await crud.get_task(task_id)
    if not task:
        return json.dumps({"error": "Task not found"})
    return json.dumps(task.model_dump(), default=str)


@mcp_server.tool()
async def analyze_user(sec_user_id: str) -> str:
    """Analyze a user's content data — engagement stats, posting frequency, video/note ratio.

    Args:
        sec_user_id: The user's sec_user_id
    """
    result = await analyzer.analyze_user(sec_user_id)
    return json.dumps(result, ensure_ascii=False, default=str)
