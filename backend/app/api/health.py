from fastapi import APIRouter
from app.config import settings
from app.infrastructure.db.database import get_async_database

router = APIRouter(tags=["Monitoring"])


@router.get("/health")
async def health_check():
    """Health check endpoint to verify service availability."""
    db = get_async_database()
    try:
        await db.command("ping")
        mongo_status = "healthy"
    except Exception as e:
        mongo_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "mongodb": mongo_status,
        "environment": settings.ENVIRONMENT,
    }
