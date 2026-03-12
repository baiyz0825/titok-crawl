from fastapi import APIRouter

from backend.db import crud
from backend.scraper.search_scraper import SearchScraper

router = APIRouter(prefix="/api/search", tags=["search"])

_search_scraper = SearchScraper()


@router.get("/users")
async def search_users(keyword: str, local_only: bool = False):
    """Search users: local DB first, then Douyin if no local results."""
    # Search local DB
    local_results = await crud.search_users_local(keyword)
    local_items = [
        {**u.model_dump(), "source": "local"} for u in local_results
    ]

    if local_items or local_only:
        return {"items": local_items, "source": "local", "total": len(local_items)}

    # No local results, search Douyin
    try:
        douyin_results = await _search_scraper.search(keyword, "user")
        douyin_items = [
            {**r, "source": "douyin"} for r in douyin_results
        ]
        return {"items": douyin_items, "source": "douyin", "total": len(douyin_items)}
    except Exception as e:
        return {"items": [], "source": "error", "total": 0, "error": str(e)}
