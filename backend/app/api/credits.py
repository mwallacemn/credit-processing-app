from celery.result import AsyncResult
from fastapi import APIRouter, status

from app.domain.models import CreditRequest, CreditResponse
from app.infrastructure.celery_app import celery_app
from app.infrastructure.db.database import get_async_database
from app.infrastructure.tasks import process_credit

router = APIRouter(tags=["Credits"])


@router.post(
    "/credits",
    response_model=CreditResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_credit(request: CreditRequest):
    """
    1. Validates the request.
    2. Sets the user's MongoDB record status to 'processing'.
    3. Publishes a task to the Celery queue.
    4. Returns 202 Accepted with task ID.
    """
    db = get_async_database()
    users_collection = db["users"]

    # Set the user's status to 'processing' (upsert if record does not yet exist)
    await users_collection.update_one(
        {"user_id": request.user_id},
        {"$set": {"status": "processing"}},
        upsert=True,
    )

    # Publish task to Celery queue
    task = process_credit.delay(request.user_id, request.amount)

    return CreditResponse(
        task_id=task.id,
        message="Credit request accepted and queued for processing",
        status="processing",
    )


@router.get(
    "/credits/{task_id}",
)
async def get_task_status(task_id: str):
    """Check status of a queued credit task."""
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
