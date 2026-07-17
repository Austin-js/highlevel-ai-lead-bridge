"""Integration tests for health endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_process_liveness() -> None:
    """The liveness endpoint does not depend on external services."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_database_availability() -> None:
    """The readiness endpoint verifies the local database connection."""
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "environment": "development"}
