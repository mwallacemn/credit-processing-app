from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_credit_service
from app.api.schemas import CreditResponse
from app.domain.credit_task_event import CreditTaskEvent, TaskStatus
from app.main import app

client = TestClient(app)


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


def test_post_credits_success():
    mock_service = MagicMock()
    mock_service.submit_credit = AsyncMock(
        return_value=CreditResponse(
            task_id="mock-task-id-12345",
            message="Credit request accepted and queued for processing",
            status=TaskStatus.PROCESSING,
        )
    )

    app.dependency_overrides[get_user_credit_service] = lambda: mock_service
    try:
        response = client.post("/credits", json={"user_id": "u_123", "amount": 150.00})
        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "mock-task-id-12345"
        assert data["status"] == "processing"
        mock_service.submit_credit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.credits.AsyncResult")
def test_get_task_status_completed(mock_async_result):
    mock_instance = MagicMock()
    mock_instance.status = "SUCCESS"
    mock_instance.ready.return_value = True
    mock_instance.result = {"user_id": "u_123", "balance": 150.00, "status": "processed"}
    mock_async_result.return_value = mock_instance

    mock_service = MagicMock()
    mock_service.get_task_event = AsyncMock(
        return_value=CreditTaskEvent(
            task_id="mock-task-123",
            user_id="u_123",
            amount=150.00,
            status=TaskStatus.PROCESSED,
        )
    )

    app.dependency_overrides[get_user_credit_service] = lambda: mock_service
    try:
        response = client.get("/credits/mock-task-123")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "mock-task-123"
        assert data["status"] == "SUCCESS"
        assert data["task_status"] == "processed"
        assert data["amount"] == 150.00
        assert data["result"]["balance"] == 150.00
    finally:
        app.dependency_overrides.clear()


@patch("app.api.credits.AsyncResult")
def test_get_task_status_pending_or_unknown_in_db(mock_async_result):
    mock_instance = MagicMock()
    mock_instance.status = "PENDING"
    mock_instance.ready.return_value = False
    mock_async_result.return_value = mock_instance

    mock_service = MagicMock()
    mock_service.get_task_event = AsyncMock(return_value=None)

    app.dependency_overrides[get_user_credit_service] = lambda: mock_service
    try:
        response = client.get("/credits/unknown-task-id")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "unknown-task-id"
        assert data["status"] == "PENDING"
        assert data["task_status"] is None
        assert data["amount"] is None
        assert data["error_message"] is None
        assert data["result"] is None
    finally:
        app.dependency_overrides.clear()
