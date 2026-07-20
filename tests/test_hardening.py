"""Tests for production safety controls."""

import logging

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import JsonFormatter
from app.core.privacy import contact_log_context
from app.domain.leads import Lead
from app.main import app


def test_contact_log_context_redacts_email_and_phone() -> None:
    """Structured log context retains only a hash and last four phone digits."""
    context = contact_log_context(
        Lead(
            contact_id="contact_001",
            full_name="Maria Santos",
            email="maria.santos@example.com",
            phone="+639171234567",
        ),
        "evt_001",
    )

    assert context["contact_id"] == "contact_001"
    assert context["email_hash"] != "maria.santos@example.com"
    assert context["phone_last4"] == "4567"
    assert "email" not in context
    assert "phone" not in context


def test_json_formatter_only_includes_allowlisted_contact_metadata() -> None:
    """The formatter does not serialize arbitrary logging extras such as raw PII."""
    record = logging.LogRecord("test", logging.INFO, "", 0, "event_received", (), None)
    record.event_id = "evt_001"  # type: ignore[attr-defined]
    record.email_hash = "hashed"  # type: ignore[attr-defined]
    record.email = "maria.santos@example.com"  # type: ignore[attr-defined]

    rendered = JsonFormatter().format(record)

    assert '"event_id": "evt_001"' in rendered
    assert '"email_hash": "hashed"' in rendered
    assert "maria.santos@example.com" not in rendered


def test_oversized_webhook_is_rejected_before_payload_validation(monkeypatch) -> None:
    """Request-size enforcement protects the webhook route from large bodies."""
    monkeypatch.setenv("MAX_REQUEST_SIZE_BYTES", "1024")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/highlevel",
            headers={"X-Webhook-Secret": "unused"},
            content=b"x" * 1025,
        )
    get_settings.cache_clear()

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds the 1024-byte limit."}
