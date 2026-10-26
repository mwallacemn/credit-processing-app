import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.infrastructure.tasks as tasks_module
from app.infrastructure.tasks import (
    _get_worker_loop,
    _revoke_celery_tasks,
    enqueue_credit_task,
    process_credit,
)


@patch.object(tasks_module.process_credit, "apply_async")
def test_enqueue_credit_task_dispatches_celery_task(mock_apply_async):
    enqueue_credit_task("task-xyz")
    mock_apply_async.assert_called_once_with(args=["task-xyz"], task_id="task-xyz")


def test_worker_loop_is_reused_across_calls():
    loop1 = _get_worker_loop()
    loop2 = _get_worker_loop()
    assert loop1 is loop2
    assert not loop1.is_closed()


def test_worker_loop_recreates_if_closed():
    loop1 = _get_worker_loop()
    loop1.close()
    loop2 = _get_worker_loop()
    assert loop2 is not loop1
    assert not loop2.is_closed()


@patch("app.infrastructure.tasks.celery_app.control.revoke")
def test_revoke_celery_tasks_calls_control_revoke(mock_revoke):
    _revoke_celery_tasks(["task-a", "task-b"])
    mock_revoke.assert_called_once_with(["task-a", "task-b"], terminate=False)


@patch("app.infrastructure.tasks.MongoUserRepository")
@patch("app.infrastructure.tasks.CreditTaskService")
def test_process_credit_task_executes_credit_task_service(mock_service_cls, mock_repo_cls):
    mock_repo_instance = MagicMock()
    mock_repo_cls.return_value = mock_repo_instance

    mock_service_instance = MagicMock()
    mock_service_instance.execute = AsyncMock(
        return_value={
            "task_id": "task-123",
            "user_id": "u_123",
            "balance": 150.0,
            "status": "processed",
        }
    )
    mock_service_cls.return_value = mock_service_instance

    result = process_credit("task-123")

    assert result["task_id"] == "task-123"
    assert result["balance"] == 150.0
    assert result["status"] == "processed"
    mock_service_instance.execute.assert_called_once_with("task-123")


@patch("app.infrastructure.tasks.MongoUserRepository")
@patch("app.infrastructure.tasks.CreditTaskService")
@patch.object(tasks_module.process_credit, "retry")
def test_process_credit_task_retries_on_exception(mock_retry, mock_service_cls, mock_repo_cls):
    mock_repo_cls.return_value = MagicMock()

    db_error = RuntimeError("transient mongo timeout")
    mock_service_instance = MagicMock()
    mock_service_instance.execute = AsyncMock(side_effect=db_error)
    mock_service_cls.return_value = mock_service_instance

    mock_retry.side_effect = RuntimeError("celery-retry-triggered")

    with pytest.raises(RuntimeError, match="celery-retry-triggered"):
        process_credit("task-err-1")

    mock_retry.assert_called_once()
