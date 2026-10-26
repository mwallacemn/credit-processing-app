from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_user_credit_service
from app.api.schemas import CreditRequest, CreditResponse
from app.infrastructure.celery_app import celery_app
from app.use_cases.user_credit_service import UserCreditService

router = APIRouter(tags=["Credits"])


@router.post(
    "/credits",
    response_model=CreditResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_credit(
    request: CreditRequest,
    service: UserCreditService = Depends(get_user_credit_service),
):
    """
    1. Validates the request.
    2. Creates a CreditTaskEvent in MongoDB (status='processing').
    3. Sets the user's MongoDB record status to 'processing'.
    4. Publishes the task to the Celery queue with the task event's task_id.
    5. Returns 202 Accepted with task ID.
    """
    return await service.submit_credit(request)


@router.get(
    "/credits/{task_id}",
)
async def get_task_status(
    task_id: str,
    service: UserCreditService = Depends(get_user_credit_service),
):
    """Check status of a queued credit task from both MongoDB and Celery."""
    result = AsyncResult(task_id, app=celery_app)
    task_event = await service.get_task_event(task_id)

    return {
        "task_id": task_id,
        "status": result.status,
        "task_status": task_event.status if task_event else None,
        "amount": task_event.amount if task_event else None,
        "error_message": task_event.error_message if task_event else None,
        "result": result.result if result.ready() else None,
    }
