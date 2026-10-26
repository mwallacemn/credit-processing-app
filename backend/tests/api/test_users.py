from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_credit_service
from app.domain.user import User, UserStatus
from app.main import app

client = TestClient(app)


def test_get_user_success():
    mock_service = MagicMock()
    mock_service.get_user = AsyncMock(
        return_value=User(user_id="u_123", balance=150.00, status=UserStatus.PROCESSED)
    )

    app.dependency_overrides[get_user_credit_service] = lambda: mock_service
    try:
        response = client.get("/users/u_123")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "u_123"
        assert data["balance"] == 150.00
        assert data["status"] == "processed"
    finally:
        app.dependency_overrides.clear()


def test_get_user_not_found():
    mock_service = MagicMock()
    mock_service.get_user = AsyncMock(return_value=None)

    app.dependency_overrides[get_user_credit_service] = lambda: mock_service
    try:
        response = client.get("/users/nonexistent")
        assert response.status_code == 404
        assert response.json()["detail"] == "User nonexistent not found"
    finally:
        app.dependency_overrides.clear()
