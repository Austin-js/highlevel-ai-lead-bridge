"""Mocked tests for isolated HighLevel CRM synchronization."""

import json

import httpx
import pytest

from app.clients.highlevel import HighLevelClient
from app.domain.leads import Lead
from app.domain.processed import ProcessedLeadEvent
from app.domain.summaries import LeadSummary
from app.services.highlevel_sync import HighLevelContactSync


def _event() -> ProcessedLeadEvent:
    return ProcessedLeadEvent(
        event_id="evt_demo_001",
        lead=Lead(contact_id="contact_demo_001", full_name="Maria Santos"),
        summary=LeadSummary(
            overview="Maria is interested in dental implants.",
            intent="Dental implants",
            urgency="high",
            qualification="high_intent",
            recommended_action="Call within 15 minutes.",
            confidence=0.9,
        ),
        fallback_used=False,
    )


@pytest.mark.asyncio
async def test_highlevel_sync_adds_note_tags_and_configured_custom_field() -> None:
    """The supported CRM operations use the expected contact endpoints and payloads."""
    requests: list[tuple[str, str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, json.loads(request.content)))
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(201, request=request)

    client = HighLevelClient(
        base_url="https://services.leadconnectorhq.com",
        api_token="test-token",
        timeout_seconds=5,
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )
    sync = HighLevelContactSync(client, "ai-reviewed", "high-intent", "field_action")

    result = await sync.sync(_event())

    expected_note = (
        "AI Lead Summary\nOverview: Maria is interested in dental implants.\nUrgency: high\n"
        "Qualification: high_intent\nRecommended action: Call within 15 minutes."
    )
    assert result.success is True
    assert requests == [
        (
            "POST",
            "/contacts/contact_demo_001/notes",
            {"body": expected_note},
        ),
        ("POST", "/contacts/contact_demo_001/tags", {"tags": ["ai-reviewed", "high-intent"]}),
        (
            "PUT",
            "/contacts/contact_demo_001",
            {"customFields": [{"id": "field_action", "value": "Call within 15 minutes."}]},
        ),
    ]


@pytest.mark.asyncio
async def test_highlevel_operation_failure_is_reported_without_stopping_other_operations() -> None:
    """One HighLevel error does not prevent the remaining configured actions."""

    def handler(request: httpx.Request) -> httpx.Response:
        status_code = 400 if request.url.path.endswith("/notes") else 201
        return httpx.Response(status_code, request=request)

    client = HighLevelClient(
        base_url="https://services.leadconnectorhq.com",
        api_token="test-token",
        timeout_seconds=5,
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )
    sync = HighLevelContactSync(client, "ai-reviewed", "high-intent", None)

    result = await sync.sync(_event())

    assert result.success is False
    assert result.warnings == ["HighLevel contact note could not be created."]
