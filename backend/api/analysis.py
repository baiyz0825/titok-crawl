from fastapi import APIRouter, HTTPException

from backend.analysis.analyzer import analyzer

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/user/{sec_user_id}")
async def analyze_user(sec_user_id: str):
    """Get user data analysis report."""
    result = await analyzer.analyze_user(sec_user_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/overview")
async def get_overview():
    """Get system overview statistics."""
    return await analyzer.get_overview()
