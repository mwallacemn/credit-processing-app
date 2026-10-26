import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.infrastructure.db.database as db_module
from app.infrastructure.db.database import get_async_database, lifespan


@pytest.mark.asyncio
@patch("app.infrastructure.db.database.get_async_database")
async def test_lifespan_provisions_mongodb_indexes(mock_get_async_db):
    mock_users_col = MagicMock()
    mock_users_col.create_index = AsyncMock()
    mock_tasks_col = MagicMock()
    mock_tasks_col.create_index = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = (
        lambda name: mock_users_col if name == "users" else mock_tasks_col
    )
    mock_get_async_db.return_value = mock_db

    async with lifespan(MagicMock()):
        pass

    mock_users_col.create_index.assert_called_once_with("user_id", unique=True)
    assert mock_tasks_col.create_index.call_count == 2
    mock_tasks_col.create_index.assert_any_call("task_id", unique=True)
    mock_tasks_col.create_index.assert_any_call([("user_id", 1), ("amount", 1), ("created_at", -1)])


@patch("app.infrastructure.db.database.AsyncIOMotorClient")
def test_get_async_database_initializes_and_reuses_client(mock_motor_cls):
    original_client = db_module.async_mongo_client
    try:
        db_module.async_mongo_client = None
        mock_client_instance = MagicMock()
        mock_motor_cls.return_value = mock_client_instance

        db1 = get_async_database()
        db2 = get_async_database()

        assert db1 is db2
        mock_motor_cls.assert_called_once()
    finally:
        db_module.async_mongo_client = original_client
