from fastapi import APIRouter

from backend.api.sessions import router as sessions_router
from backend.api.users import router as users_router
from backend.api.works import router as works_router
from backend.api.tasks import router as tasks_router
from backend.api.analysis import router as analysis_router
from backend.api.search import router as search_router
from backend.api.logs import router as logs_router
from backend.api.favorites import router as favorites_router
from backend.api.schedules import router as schedules_router

api_router = APIRouter()
api_router.include_router(sessions_router)
api_router.include_router(users_router)
api_router.include_router(works_router)
api_router.include_router(tasks_router)
api_router.include_router(analysis_router)
api_router.include_router(search_router)
api_router.include_router(logs_router)
api_router.include_router(favorites_router)
api_router.include_router(schedules_router)
