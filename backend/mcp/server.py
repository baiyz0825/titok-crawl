import json
import logging

from mcp.server.fastmcp import FastMCP

from backend.db import crud
from backend.analysis.analyzer import analyzer
from backend.config import settings

logger = logging.getLogger(__name__)

mcp_server = FastMCP("douyin-scraper", host="0.0.0.0", port=settings.MCP_PORT)


@mcp_server.tool()
async def scrape_user(sec_user_id: str) -> str:
    """Scrape a Douyin user's profile data. Creates a background task.

    Args:
        sec_user_id: The user's sec_user_id from their profile URL
    """
    task = await crud.create_task(
        task_type="user_profile",
        params={"sec_user_id": sec_user_id},
    )
    return json.dumps({"task_id": task.id, "status": "pending", "message": f"Task created to scrape user {sec_user_id}"})


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
async def get_user_info(sec_user_id: str) -> str:
    """Get stored user profile information from database.

    Args:
        sec_user_id: The user's sec_user_id
    """
    user = await crud.get_user(sec_user_id)
    if not user:
        return json.dumps({"error": "User not found in database"})
    return json.dumps(user.model_dump(), ensure_ascii=False, default=str)


@mcp_server.tool()
async def get_works(sec_user_id: str | None = None, work_type: str | None = None, page: int = 1, size: int = 20) -> str:
    """Get stored works from database with optional filters.

    Args:
        sec_user_id: Filter by user (optional)
        work_type: Filter by type: 'video' or 'note' (optional)
        page: Page number (default 1)
        size: Page size (default 20)
    """
    works = await crud.get_works(sec_user_id=sec_user_id, work_type=work_type, page=page, size=size)
    total = await crud.count_works(sec_user_id=sec_user_id, work_type=work_type)
    return json.dumps({"items": [w.model_dump() for w in works], "total": total}, ensure_ascii=False, default=str)


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
