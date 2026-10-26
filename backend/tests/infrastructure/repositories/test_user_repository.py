from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from pymongo import ReturnDocument

from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.domain.user import UserStatus
from app.infrastructure.repositories.user_repository import MongoUserRepository


def _create_mock_db():
    mock_db = MagicMock()
    mock_users = MagicMock()
    mock_tasks = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: mock_users if name == "users" else mock_tasks
    return mock_db, mock_users, mock_tasks


@pytest.mark.asyncio
async def test_repository_get_user_and_updates():
    mock_db, mock_users, _ = _create_mock_db()
    mock_users.find_one = AsyncMock(
        return_value={"user_id": "u_123", "balance": 200.0, "status": "processed"}
    )
    mock_users.find_one_and_update = AsyncMock(
        return_value={"user_id": "u_123", "balance": 250.0, "status": "processed"}
    )

    repo = MongoUserRepository(db=mock_db)

    user = await repo.get_user("u_123")
    assert user is not None
    assert user.user_id == "u_123"
    assert user.balance == 200.0
    assert user.status == "processed"

    updated = await repo.increment_user_balance("u_123", 50.0, status=UserStatus.PROCESSED)
    assert updated.balance == 250.0
    mock_users.find_one_and_update.assert_called_once_with(
        {"user_id": "u_123"},
        {"$inc": {"balance": 50.0}, "$set": {"status": "processed"}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


@pytest.mark.asyncio
async def test_repository_get_user_returns_none_when_missing():
    mock_db, mock_users, _ = _create_mock_db()
    mock_users.find_one = AsyncMock(return_value=None)

    repo = MongoUserRepository(db=mock_db)
    assert await repo.get_user("missing_user") is None


@pytest.mark.asyncio
async def test_repository_update_user_status_upserts():
    mock_db, mock_users, _ = _create_mock_db()
    mock_users.find_one_and_update = AsyncMock(
        return_value={"user_id": "u_123", "balance": 0.0, "status": "processing"}
    )

    repo = MongoUserRepository(db=mock_db)
    user = await repo.update_user_status("u_123", UserStatus.PROCESSING)

    assert user.user_id == "u_123"
    assert user.status == UserStatus.PROCESSING
    mock_users.find_one_and_update.assert_called_once_with(
        {"user_id": "u_123"},
        {"$set": {"status": UserStatus.PROCESSING}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


@pytest.mark.asyncio
async def test_create_credit_task_accepts_processing_status():
    mock_db, _, mock_tasks = _create_mock_db()
    mock_tasks.insert_one = AsyncMock()

    repo = MongoUserRepository(db=mock_db)
    task = CreditTaskEvent(user_id="u_123", amount=100.0, status=TaskStatus.PROCESSING)

    saved = await repo.create_credit_task(task)
    assert saved.task_id == task.task_id
    assert saved.status == TaskStatus.PROCESSING
    mock_tasks.insert_one.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_status",
    [
        TaskStatus.REVOKED_DUPLICATE,
        TaskStatus.FAILED_DUPLICATE,
        TaskStatus.PROCESSED,
        TaskStatus.FAILED,
    ],
)
async def test_create_credit_task_rejects_non_processing_initial_status(invalid_status):
    mock_db, _, mock_tasks = _create_mock_db()
    mock_tasks.insert_one = AsyncMock()

    repo = MongoUserRepository(db=mock_db)
    invalid_task = CreditTaskEvent(user_id="u_123", amount=100.0, status=invalid_status)

    with pytest.raises(ValueError, match="must be created with status='processing'"):
        await repo.create_credit_task(invalid_task)

    mock_tasks.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_get_credit_task_found_and_not_found():
    mock_db, _, mock_tasks = _create_mock_db()
    now = datetime.now(timezone.utc)
    mock_tasks.find_one = AsyncMock(
        side_effect=[
            {
                "task_id": "t_100",
                "user_id": "u_123",
                "amount": 50.0,
                "status": "processing",
                "created_at": now,
                "updated_at": now,
            },
            None,
        ]
    )

    repo = MongoUserRepository(db=mock_db)
    found = await repo.get_credit_task("t_100")
    assert found is not None
    assert found.task_id == "t_100"

    missing = await repo.get_credit_task("t_missing")
    assert missing is None


@pytest.mark.asyncio
async def test_update_credit_task_status_prevents_overwriting_revoked_or_terminal_state():
    mock_db, _, mock_tasks = _create_mock_db()
    # When a record is already in 'revoked_duplicate', the filter {"status": "processing"} matches nothing (None)
    mock_tasks.find_one_and_update = AsyncMock(return_value=None)

    repo = MongoUserRepository(db=mock_db)
    result = await repo.update_credit_task_status("task-revoked-1", TaskStatus.PROCESSED)

    assert result is None
    call_filter = mock_tasks.find_one_and_update.call_args[0][0]
    assert call_filter == {
        "task_id": "task-revoked-1",
        "status": TaskStatus.PROCESSING,
    }


@pytest.mark.asyncio
async def test_update_credit_task_status_sets_error_message_when_provided():
    mock_db, _, mock_tasks = _create_mock_db()
    now = datetime.now(timezone.utc)
    mock_tasks.find_one_and_update = AsyncMock(
        return_value={
            "task_id": "t_dup",
            "user_id": "u_123",
            "amount": 50.0,
            "status": TaskStatus.FAILED_DUPLICATE,
            "error_message": "Duplicate detected",
            "created_at": now,
            "updated_at": now,
        }
    )

    repo = MongoUserRepository(db=mock_db)
    updated = await repo.update_credit_task_status(
        "t_dup", TaskStatus.FAILED_DUPLICATE, error_message="Duplicate detected"
    )

    assert updated is not None
    assert updated.status == TaskStatus.FAILED_DUPLICATE
    assert updated.error_message == "Duplicate detected"
    update_doc = mock_tasks.find_one_and_update.call_args[0][1]
    assert update_doc["$set"]["error_message"] == "Duplicate detected"


@pytest.mark.asyncio
async def test_find_recent_tasks_by_amount_excludes_failed_duplicates():
    mock_db, _, mock_tasks = _create_mock_db()
    now = datetime.now(timezone.utc)

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "task_id": "t_1",
                "user_id": "u_123",
                "amount": 100.0,
                "status": "processed",
                "created_at": now,
                "updated_at": now,
            }
        ]
    )
    mock_tasks.find.return_value = mock_cursor

    repo = MongoUserRepository(db=mock_db)
    results = await repo.find_recent_tasks_by_amount("u_123", 100.0, since=now, exclude_task_id="t_2")

    assert len(results) == 1
    assert results[0].task_id == "t_1"
    query_passed = mock_tasks.find.call_args[0][0]
    assert query_passed["status"] == {"$in": ["processing", "processed"]}
    assert query_passed["task_id"] == {"$ne": "t_2"}


@pytest.mark.asyncio
async def test_count_active_tasks_for_user():
    mock_db, _, mock_tasks = _create_mock_db()
    mock_tasks.count_documents = AsyncMock(return_value=2)

    repo = MongoUserRepository(db=mock_db)
    count = await repo.count_active_tasks_for_user("u_123", exclude_task_id="t_99")

    assert count == 2
    mock_tasks.count_documents.assert_called_once_with(
        {
            "user_id": "u_123",
            "status": TaskStatus.PROCESSING,
            "task_id": {"$ne": "t_99"},
        }
    )
