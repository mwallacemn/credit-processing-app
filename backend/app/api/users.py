from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_user_credit_service
from app.api.schemas import UserResponse
from app.use_cases.user_credit_service import UserCreditService

router = APIRouter(tags=["Users"])


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
)
async def get_user(
    user_id: str,
    service: UserCreditService = Depends(get_user_credit_service),
):
    """Fetch user balance and status via UserCreditService."""
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return UserResponse.from_user(user)
