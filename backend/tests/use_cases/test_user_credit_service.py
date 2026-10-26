import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.schemas import CreditRequest
from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.user import User, UserStatus
from app.use_cases.user_credit_service import UserCreditService


@pytest.mark.asyncio
async def test_user_credit_service_creates_processing_task_and_dispatches_enqueue_callback():
    mock_repo = AsyncMock()
    mock_repo.create_credit_task.side_effect = lambda event: event
    mock_repo.update_user_status.return_value = User(
        user_id="u_123", balance=0.0, status=UserStatus.PROCESSING
    )
    enqueue_mock = MagicMock()

    service = UserCreditService(user_repository=mock_repo, enqueue_callback=enqueue_mock)
    response = await service.submit_credit(CreditRequest(user_id="u_123", amount=150.0))

    assert response.status == TaskStatus.PROCESSING
    assert len(response.task_id) > 0

    # Verify task event was saved with status='processing'
    saved_event: CreditTaskEvent = mock_repo.create_credit_task.call_args[0][0]
    assert saved_event.user_id == "u_123"
    assert saved_event.amount == 150.0
    assert saved_event.status == TaskStatus.PROCESSING

    # Verify user status updated to 'processing'
    mock_repo.update_user_status.assert_called_once_with("u_123", UserStatus.PROCESSING)

    # Verify enqueue callback dispatched with matching task_id
    enqueue_mock.assert_called_once_with(response.task_id)


@pytest.mark.asyncio
async def test_user_credit_service_query_methods_delegate_to_repository():
    mock_repo = AsyncMock()
    expected_user = User(user_id="u_123", balance=100.0, status=UserStatus.PROCESSED)
    expected_task = CreditTaskEvent(task_id="t_123", user_id="u_123", amount=100.0)
    mock_repo.get_user.return_value = expected_user
    mock_repo.get_credit_task.return_value = expected_task

    service = UserCreditService(user_repository=mock_repo)

    assert await service.get_user("u_123") == expected_user
    assert await service.get_task_event("t_123") == expected_task
    mock_repo.get_user.assert_called_once_with("u_123")
    mock_repo.get_credit_task.assert_called_once_with("t_123")
