from fastapi import APIRouter

from app.api.credits import router as credits_router
from app.api.health import router as health_router
from app.api.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(credits_router)
api_router.include_router(users_router)
