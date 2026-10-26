from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_healthy():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mongodb"] == "healthy"


@patch("app.api.health.get_async_database")
def test_health_endpoint_reports_unhealthy_mongodb_on_ping_failure(mock_get_db):
    mock_db = MagicMock()
    mock_db.command = AsyncMock(side_effect=RuntimeError("connection refused"))
    mock_get_db.return_value = mock_db

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "unhealthy: connection refused" in data["mongodb"]
