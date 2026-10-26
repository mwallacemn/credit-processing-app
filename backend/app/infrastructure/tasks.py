import asyncio
import logging
from typing import List

from app.infrastructure.celery_app import celery_app
from app.infrastructure.repositories.user_repository import MongoUserRepository
from app.use_cases.user_credit_service import UserCreditService

logger = logging.getLogger(__name__)

# Persistent worker event loop so Motor AsyncIOMotorClient stays bound to the same loop
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def _revoke_celery_tasks(task_ids: List[str]) -> None:
    celery_app.control.revoke(task_ids, terminate=False)


def enqueue_credit_task(task_id: str) -> None:
    process_credit.apply_async(args=[task_id], task_id=task_id)


@celery_app.task(name="app.infrastructure.tasks.process_credit", bind=True, max_retries=3)
def process_credit(self, credit_task_id: str) -> dict:
    """
    Celery task that instantiates UserCreditService to validate and apply a credit task event.
    """
    logger.info(f"Executing UserCreditService.execute_credit_task for task_id={credit_task_id}")
    loop = _get_worker_loop()
    repository = MongoUserRepository()
    service = UserCreditService(
        user_repository=repository,
        revoke_callback=_revoke_celery_tasks,
    )

    try:
        return loop.run_until_complete(service.execute_credit_task(credit_task_id))
    except Exception as exc:
        logger.error(f"Error processing credit task {credit_task_id}: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
