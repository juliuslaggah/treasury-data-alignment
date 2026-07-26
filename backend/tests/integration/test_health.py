from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_service_status() -> None:
    """The health endpoint should confirm that the API is operational."""

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["service"] == "Treasury Data Alignment API"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "development"
    assert isinstance(payload["timestamp"], str)

    