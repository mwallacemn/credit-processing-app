import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.tasks import process_credit

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_post_credits_validation_invalid_amount():
    # Negative amount should be rejected with 422
    response = client.post("/credits", json={"user_id": "u_123", "amount": -10.0})
    assert response.status_code == 422

    # Zero amount should be rejected with 422
    response = client.post("/credits", json={"user_id": "u_123", "amount": 0})
    assert response.status_code == 422


def test_post_credits_validation_missing_fields():
    response = client.post("/credits", json={"amount": 100})
    assert response.status_code == 422

    response = client.post("/credits", json={"user_id": ""})
    assert response.status_code == 422


@patch("app.api.credits.process_credit.delay")
@patch("app.api.credits.get_async_database")
def test_post_credits_success(mock_get_db, mock_celery_delay):
    # Mock celery task
    mock_task = MagicMock()
    mock_task.id = "mock-task-id-12345"
    mock_celery_delay.return_value = mock_task

    # Mock MongoDB update
    mock_collection = MagicMock()
    mock_db = {"users": mock_collection}
    mock_get_db.return_value = mock_db

    import asyncio
    future = asyncio.Future()
    future.set_result(None)
    mock_collection.update_one.return_value = future

    response = client.post("/credits", json={"user_id": "u_123", "amount": 150.00})
    assert response.status_code == 202
    data = response.json()
    assert data["task_id"] == "mock-task-id-12345"
    assert data["status"] == "processing"
    mock_celery_delay.assert_called_once_with("u_123", 150.00)


@patch("app.api.users.get_async_database")
def test_get_user_success(mock_get_db):
    mock_collection = MagicMock()
    mock_db = {"users": mock_collection}
    mock_get_db.return_value = mock_db

    import asyncio
    future = asyncio.Future()
    future.set_result({"user_id": "u_123", "balance": 150.00, "status": "processed"})
    mock_collection.find_one.return_value = future

    response = client.get("/users/u_123")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "u_123"
    assert data["balance"] == 150.00
    assert data["status"] == "processed"


@patch("app.api.users.get_async_database")
def test_get_user_not_found(mock_get_db):
    mock_collection = MagicMock()
    mock_db = {"users": mock_collection}
    mock_get_db.return_value = mock_db

    import asyncio
    future = asyncio.Future()
    future.set_result(None)
    mock_collection.find_one.return_value = future

    response = client.get("/users/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "User nonexistent not found"


@patch("app.api.credits.AsyncResult")
def test_get_task_status(mock_async_result):
    mock_instance = MagicMock()
    mock_instance.status = "SUCCESS"
    mock_instance.ready.return_value = True
    mock_instance.result = {"user_id": "u_123", "balance": 150.00, "status": "processed"}
    mock_async_result.return_value = mock_instance

    response = client.get("/credits/mock-task-123")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "mock-task-123"
    assert data["status"] == "SUCCESS"
    assert data["result"]["balance"] == 150.00


@patch("app.infrastructure.tasks.get_sync_database")
def test_process_credit_task(mock_get_sync_db):
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    mock_get_sync_db.return_value = mock_db

    mock_collection.find_one_and_update.return_value = {
        "user_id": "u_123",
        "balance": 150.00,
        "status": "processed",
    }

    result = process_credit("u_123", 150.00)

    assert result["user_id"] == "u_123"
    assert result["balance"] == 150.00
    assert result["status"] == "processed"
    mock_collection.find_one_and_update.assert_called_once_with(
        {"user_id": "u_123"},
        {
            "$inc": {"balance": 150.00},
            "$set": {"status": "processed"},
        },
        return_document=True,
        upsert=True,
    )
