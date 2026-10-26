from datetime import datetime, timedelta, timezone
import logging
from typing import Callable, List, Optional

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.interfaces import IUserInterface
from app.domain.user import UserStatus

logger = logging.getLogger(__name__)

DUPLICATE_WINDOW_MINUTES = 5


class CreditTaskService:
    """
    Dedicated worker use-case service for validating, revoking, and executing credit tasks:
    - Checks 5-minute rolling duplicate window for (user_id, amount)
    - Pre-emptively revokes newer queued duplicate Celery tasks
    - Atomically updates task status to 'processed' and increments user balance
    - Reconciles user account status upon duplicate failure
    """

    def __init__(
        self,
        user_repository: IUserInterface,
        revoke_callback: Optional[Callable[[List[str]], None]] = None,
    ):
        self._repo = user_repository
        self._revoke_callback = revoke_callback

    async def execute(self, task_id: str) -> dict:
        task_event = await self._repo.get_credit_task(task_id)
        if not task_event:
            raise ValueError(f"CreditTaskEvent {task_id} not found in database")

        # If already revoked or failed, exit idempotently
        if task_event.had_failed:
            logger.warning(f"Task {task_id} was already marked as {task_event.status}. Skipping.")
            return {
                "task_id": task_id,
                "user_id": task_event.user_id,
                "status": task_event.status,
                "error": task_event.error_message,
            }

        if task_event.status == TaskStatus.PROCESSED:
            user = await self._repo.get_user(task_event.user_id)
            return {
                "task_id": task_id,
                "user_id": task_event.user_id,
                "balance": user.balance if user else 0.0,
                "status": TaskStatus.PROCESSED,
            }

        # Check all recent tasks for the same user and balance amount within the last 5 minutes
        window_start = datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
        recent_matching_tasks = await self._repo.find_recent_tasks_by_amount(
            user_id=task_event.user_id,
            amount=task_event.amount,
            since=window_start,
            exclude_task_id=task_id,
        )

        # Separate into:
        # 1) Earlier or already-processed tasks (meaning THIS task is a duplicate)
        # 2) Newer 'processing' tasks (meaning THOSE tasks in the queue are duplicates to revoke)
        earlier_or_completed = [
            t for t in recent_matching_tasks
            if t.status == TaskStatus.PROCESSED or t.created_at <= task_event.created_at
        ]
        newer_duplicates_to_revoke = [
            t.task_id for t in recent_matching_tasks
            if t.status == TaskStatus.PROCESSING and t.created_at > task_event.created_at
        ]

        # Attempt to revoke any newer duplicate tasks from the Celery queue
        if newer_duplicates_to_revoke:
            await self._revoke_other_tasks(newer_duplicates_to_revoke)

        # If an earlier or already-processed task with the same amount exists within 5 mins -> FAIL as duplicate
        if earlier_or_completed:
            error_msg = (
                f"Duplicate credit of {task_event.amount} for user {task_event.user_id} "
                f"detected within the last {DUPLICATE_WINDOW_MINUTES} minutes."
            )
            logger.warning(f"Task {task_id} failed validation: {error_msg}")
            await self._repo.update_credit_task_status(
                task_id, TaskStatus.FAILED_DUPLICATE, error_message=error_msg
            )
            await self._reconcile_user_status_after_failure(task_event.user_id, task_id)
            return {
                "task_id": task_id,
                "user_id": task_event.user_id,
                "status": TaskStatus.FAILED_DUPLICATE,
                "error": error_msg,
            }

        # Guard: transition task status from 'processing' -> 'processed' first.
        # If another worker revoked this task concurrently, transitioned_task will be None!
        transitioned_task = await self._repo.update_credit_task_status(
            task_id, TaskStatus.PROCESSED
        )
        if not transitioned_task:
            logger.warning(f"Task {task_id} was concurrently modified/revoked. Aborting balance update.")
            latest = await self._repo.get_credit_task(task_id)
            return {
                "task_id": task_id,
                "user_id": task_event.user_id,
                "status": latest.status if latest else TaskStatus.REVOKED_DUPLICATE,
            }

        # Valid credit: atomically increment user balance and set user status to 'processed'
        updated_user = await self._repo.increment_user_balance(
            user_id=task_event.user_id,
            amount=task_event.amount,
            status=UserStatus.PROCESSED,
        )

        return {
            "task_id": task_id,
            "user_id": updated_user.user_id,
            "balance": updated_user.balance,
            "status": UserStatus.PROCESSED,
        }

    async def _revoke_other_tasks(self, task_ids: List[str]) -> None:
        """Marks duplicate queued tasks as revoked in DB and revokes them from Celery broker."""
        for dup_id in task_ids:
            await self._repo.update_credit_task_status(
                dup_id,
                TaskStatus.REVOKED_DUPLICATE,
                error_message="Revoked from queue due to duplicate credit submission within 5 minutes.",
            )
        if self._revoke_callback:
            try:
                self._revoke_callback(task_ids)
                logger.info(f"Revoked duplicate Celery tasks from queue: {task_ids}")
            except Exception as exc:
                logger.warning(f"Failed to broadcast Celery revoke for {task_ids}: {exc}")

    async def _reconcile_user_status_after_failure(self, user_id: str, failed_task_id: str) -> None:
        """Ensures user document doesn't stay stuck in 'processing' if no other tasks are active."""
        active_count = await self._repo.count_active_tasks_for_user(user_id, exclude_task_id=failed_task_id)
        if active_count == 0:
            user = await self._repo.get_user(user_id)
            new_status = UserStatus.PROCESSED if (user and user.balance > 0) else UserStatus.FAILED
            await self._repo.update_user_status(user_id, new_status)
