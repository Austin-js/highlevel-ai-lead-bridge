"""Integration tests for HighLevel webhook intake."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import app


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Supply isolated configuration without creating a local env file."""
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "test-webhook-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    yield
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


def _payload(event_id: str = "evt_test_001") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "contact.created",
        "location_id": "loc_test_001",
        "contact": {
            "id": "contact_test_001",
            "first_name": "  Maria ",
            "last_name": " Santos ",
            "email": "maria.santos@example.com",
            "phone": "+63 917 123 4567",
            "source": "Facebook Ads",
            "custom_fields": {"service_requested": "Dental implants"},
        },
    }


def test_valid_webhook_is_persisted() -> None:
    """An authenticated payload is accepted and acknowledged."""
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "test-webhook-secret"},
            json=_payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "event_id": "evt_test_001",
        "duplicate": False,
        "fallback_used": False,
    }


def test_missing_secret_is_rejected() -> None:
    """A webhook must include credentials."""
    with TestClient(app) as client:
        response = client.post("/webhooks/highlevel", json=_payload("evt_missing_secret"))

    assert response.status_code == 401


def test_invalid_secret_is_rejected() -> None:
    """A non-matching secret is forbidden."""
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "not-the-secret"},
            json=_payload("evt_invalid_secret"),
        )

    assert response.status_code == 403


def test_duplicate_event_is_not_persisted_twice() -> None:
    """Repeated events receive a successful duplicate acknowledgement."""
    event = _payload("evt_duplicate_test")
    headers = {"X-Webhook-Secret": "test-webhook-secret"}
    with TestClient(app) as client:
        first_response = client.post("/webhooks/highlevel", headers=headers, json=event)
        duplicate_response = client.post("/webhooks/highlevel", headers=headers, json=event)

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {
        "status": "duplicate",
        "event_id": "evt_duplicate_test",
        "duplicate": True,
    }


def test_missing_optional_contact_fields_are_allowed() -> None:
    """Leads without email or phone are still accepted."""
    event = _payload("evt_optional_fields")
    event["contact"].pop("email")
    event["contact"].pop("phone")
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "test-webhook-secret"},
            json=event,
        )

    assert response.status_code == 200


def test_invalid_payload_is_rejected() -> None:
    """A payload with no contact object returns FastAPI validation feedback."""
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "test-webhook-secret"},
            json={"event_id": "evt_bad", "contact": "invalid"},
        )

    assert response.status_code == 422


def test_notification_configuration_failure_marks_event_partially_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A notification error preserves the completed summary and surfaces a warning."""
    monkeypatch.setenv("NOTIFICATION_PROVIDER", "slack")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "test-webhook-secret"},
            json=_payload("evt_notification_failure"),
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "partially_completed",
        "event_id": "evt_notification_failure",
        "duplicate": False,
        "fallback_used": False,
        "warnings": ["Slack webhook URL is not configured."],
    }


def test_highlevel_configuration_failure_marks_event_partially_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional CRM sync errors are returned without discarding the lead summary."""
    monkeypatch.setenv("HIGHLEVEL_SYNC_ENABLED", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "test-webhook-secret"},
            json=_payload("evt_highlevel_failure"),
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "partially_completed",
        "event_id": "evt_highlevel_failure",
        "duplicate": False,
        "fallback_used": False,
        "warnings": ["HIGHLEVEL_API_TOKEN is not configured."],
    }
