from fastapi import APIRouter, HTTPException

from backend.db import crud

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("")
async def list_favorites(page: int = 1, size: int = 20):
    """获取收藏列表"""
    favorites = await crud.get_favorites(page=page, size=size)
    total = await crud.count_favorites()
    return {
        "items": [fav.model_dump() for fav in favorites],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/{aweme_id}")
async def add_favorite(aweme_id: str):
    """添加收藏"""
    success = await crud.add_favorite(aweme_id)
    if not success:
        raise HTTPException(status_code=400, detail="Already favorited")
    return {"status": "added"}


@router.delete("/{aweme_id}")
async def remove_favorite(aweme_id: str):
    """取消收藏"""
    success = await crud.remove_favorite(aweme_id)
    if not success:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "removed"}


@router.get("/{aweme_id}/check")
async def check_favorite(aweme_id: str):
    """检查是否已收藏"""
    is_fav = await crud.is_favorite(aweme_id)
    return {"favorited": is_fav}
