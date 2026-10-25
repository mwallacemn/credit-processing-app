from fastapi import APIRouter, HTTPException, status

from app.domain.models import UserResponse
from app.infrastructure.db.database import get_async_database

router = APIRouter(tags=["Users"])


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
)
async def get_user(user_id: str):
    """Fetch user balance and status."""
    db = get_async_database()
    user = await db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return UserResponse(
        user_id=user.get("user_id"),
        balance=user.get("balance", 0.0),
        status=user.get("status", "unknown"),
    )
