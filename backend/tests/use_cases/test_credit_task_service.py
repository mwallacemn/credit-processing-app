from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.user import User, UserStatus
from app.use_cases.credit_task_service import CreditTaskService


@pytest.mark.asyncio
async def test_credit_task_service_execute_happy_path():
    now = datetime.now(timezone.utc)
    task_event = CreditTaskEvent(
        task_id="task-valid-1",
        user_id="u_123",
        amount=150.0,
        status=TaskStatus.PROCESSING,
        created_at=now,
    )

    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = task_event
    mock_repo.find_recent_tasks_by_amount.return_value = []
    mock_repo.update_credit_task_status.return_value = CreditTaskEvent(
        task_id="task-valid-1",
        user_id="u_123",
        amount=150.0,
        status=TaskStatus.PROCESSED,
        created_at=now,
    )
    mock_repo.increment_user_balance.return_value = User(
        user_id="u_123", balance=150.0, status=UserStatus.PROCESSED
    )

    service = CreditTaskService(user_repository=mock_repo)
    result = await service.execute("task-valid-1")

    assert result["status"] == UserStatus.PROCESSED
    assert result["balance"] == 150.0
    mock_repo.update_credit_task_status.assert_called_once_with(
        "task-valid-1", TaskStatus.PROCESSED
    )
    mock_repo.increment_user_balance.assert_called_once_with(
        user_id="u_123",
        amount=150.0,
        status=UserStatus.PROCESSED,
    )


@pytest.mark.asyncio
async def test_credit_task_service_execute_raises_when_task_not_found():
    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = None

    service = CreditTaskService(user_repository=mock_repo)
    with pytest.raises(ValueError, match="CreditTaskEvent missing-id not found"):
        await service.execute("missing-id")


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_failure_status", [TaskStatus.REVOKED_DUPLICATE, TaskStatus.FAILED_DUPLICATE])
async def test_credit_task_service_execute_skips_already_failed_or_revoked_task(terminal_failure_status):
    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = CreditTaskEvent(
        task_id="task-already-failed",
        user_id="u_123",
        amount=100.0,
        status=terminal_failure_status,
        error_message="Already rejected",
    )

    service = CreditTaskService(user_repository=mock_repo)
    result = await service.execute("task-already-failed")

    assert result["status"] == terminal_failure_status
    assert result["error"] == "Already rejected"
    mock_repo.find_recent_tasks_by_amount.assert_not_called()
    mock_repo.increment_user_balance.assert_not_called()


@pytest.mark.asyncio
async def test_credit_task_service_execute_returns_idempotently_when_already_processed():
    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = CreditTaskEvent(
        task_id="task-already-done",
        user_id="u_123",
        amount=100.0,
        status=TaskStatus.PROCESSED,
    )
    mock_repo.get_user.return_value = User(
        user_id="u_123", balance=300.0, status=UserStatus.PROCESSED
    )

    service = CreditTaskService(user_repository=mock_repo)
    result = await service.execute("task-already-done")

    assert result["status"] == TaskStatus.PROCESSED
    assert result["balance"] == 300.0
    mock_repo.increment_user_balance.assert_not_called()


@pytest.mark.asyncio
async def test_credit_task_service_rejects_duplicate_within_5_minutes_and_revokes_newer():
    now = datetime.now(timezone.utc)
    # 1. Earlier already-processed task (3 mins ago)
    earlier_task = CreditTaskEvent(
        task_id="task-1",
        user_id="u_123",
        amount=150.0,
        status=TaskStatus.PROCESSED,
        created_at=now - timedelta(minutes=3),
    )
    # 2. Currently executing duplicate task (1 min ago)
    current_task = CreditTaskEvent(
        task_id="task-2",
        user_id="u_123",
        amount=150.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(minutes=1),
    )
    # 3. Even newer duplicate sitting in the queue (10s ago)
    newer_queued_task = CreditTaskEvent(
        task_id="task-3",
        user_id="u_123",
        amount=150.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(seconds=10),
    )

    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = current_task
    mock_repo.find_recent_tasks_by_amount.return_value = [earlier_task, newer_queued_task]
    mock_repo.count_active_tasks_for_user.return_value = 0
    mock_repo.get_user.return_value = User(
        user_id="u_123", balance=150.0, status=UserStatus.PROCESSING
    )

    revoke_mock = MagicMock()
    service = CreditTaskService(user_repository=mock_repo, revoke_callback=revoke_mock)

    result = await service.execute("task-2")

    assert result["status"] == TaskStatus.FAILED_DUPLICATE
    assert "Duplicate credit" in result["error"]

    # Verify newer queued task was revoked from Celery and marked revoked_duplicate in DB
    revoke_mock.assert_called_once_with(["task-3"])

    # Verify user balance was NOT incremented a second time
    mock_repo.increment_user_balance.assert_not_called()

    # Verify user status reconciled back to 'processed' since they had a valid balance > 0
    mock_repo.update_user_status.assert_called_once_with("u_123", UserStatus.PROCESSED)


@pytest.mark.asyncio
async def test_credit_task_service_reconciles_user_to_failed_when_balance_is_zero():
    now = datetime.now(timezone.utc)
    earlier_task = CreditTaskEvent(
        task_id="task-1",
        user_id="u_zero",
        amount=50.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(minutes=2),
    )
    current_task = CreditTaskEvent(
        task_id="task-2",
        user_id="u_zero",
        amount=50.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(minutes=1),
    )

    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = current_task
    mock_repo.find_recent_tasks_by_amount.return_value = [earlier_task]
    mock_repo.count_active_tasks_for_user.return_value = 0
    mock_repo.get_user.return_value = User(
        user_id="u_zero", balance=0.0, status=UserStatus.PROCESSING
    )

    service = CreditTaskService(user_repository=mock_repo)
    result = await service.execute("task-2")

    assert result["status"] == TaskStatus.FAILED_DUPLICATE
    mock_repo.update_user_status.assert_called_once_with("u_zero", UserStatus.FAILED)


@pytest.mark.asyncio
async def test_credit_task_service_earliest_task_succeeds_and_revokes_newer_burst_duplicates():
    """
    Simulates a burst where Task 1 (T+0s) and Task 2 (T+1s) are both submitted before
    Task 1 runs. Task 1 should SUCCEED and pre-emptively revoke Task 2!
    """
    now = datetime.now(timezone.utc)
    task_1 = CreditTaskEvent(
        task_id="task-burst-1",
        user_id="u_123",
        amount=75.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(seconds=5),
    )
    task_2_newer = CreditTaskEvent(
        task_id="task-burst-2",
        user_id="u_123",
        amount=75.0,
        status=TaskStatus.PROCESSING,
        created_at=now - timedelta(seconds=1),
    )

    mock_repo = AsyncMock()
    mock_repo.get_credit_task.return_value = task_1
    mock_repo.find_recent_tasks_by_amount.return_value = [task_2_newer]
    mock_repo.update_credit_task_status.return_value = task_1
    mock_repo.increment_user_balance.return_value = User(
        user_id="u_123", balance=75.0, status=UserStatus.PROCESSED
    )

    # Even if revoke_callback raises a broker error, task 1 should still succeed
    revoke_mock = MagicMock(side_effect=RuntimeError("broker unreachable"))
    service = CreditTaskService(user_repository=mock_repo, revoke_callback=revoke_mock)

    result = await service.execute("task-burst-1")

    assert result["status"] == UserStatus.PROCESSED
    assert result["balance"] == 75.0
    revoke_mock.assert_called_once_with(["task-burst-2"])
    mock_repo.increment_user_balance.assert_called_once()


@pytest.mark.asyncio
async def test_credit_task_service_aborts_if_concurrently_revoked():
    now = datetime.now(timezone.utc)
    task_event = CreditTaskEvent(
        task_id="task-race-1",
        user_id="u_123",
        amount=100.0,
        status=TaskStatus.PROCESSING,
        created_at=now,
    )
    revoked_event = CreditTaskEvent(
        task_id="task-race-1",
        user_id="u_123",
        amount=100.0,
        status=TaskStatus.REVOKED_DUPLICATE,
        created_at=now,
    )

    mock_repo = AsyncMock()
    mock_repo.get_credit_task.side_effect = [task_event, revoked_event]
    mock_repo.find_recent_tasks_by_amount.return_value = []
    # Simulate atomic transition failing (returning None) because another worker just revoked it
    mock_repo.update_credit_task_status.return_value = None

    service = CreditTaskService(user_repository=mock_repo)
    result = await service.execute("task-race-1")

    assert result["status"] == TaskStatus.REVOKED_DUPLICATE
    mock_repo.increment_user_balance.assert_not_called()
