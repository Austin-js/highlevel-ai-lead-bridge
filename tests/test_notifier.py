"""Mocked delivery tests for Slack and Discord notification adapters."""

import json

import httpx
import pytest

from app.clients.discord import DiscordNotifier
from app.clients.slack import SlackNotifier
from app.domain.leads import Lead
from app.domain.processed import ProcessedLeadEvent
from app.domain.summaries import LeadSummary


def _event() -> ProcessedLeadEvent:
    return ProcessedLeadEvent(
        event_id="evt_demo_001",
        lead=Lead(
            full_name="Maria Santos",
            email="maria.santos@example.com",
            service_requested="Dental implants",
            preferred_schedule="Saturday morning",
            source="Facebook Ads",
        ),
        summary=LeadSummary(
            overview="Maria is interested in dental implants.",
            intent="Dental implants",
            urgency="high",
            qualification="high_intent",
            key_details=["Requested service: Dental implants"],
            missing_information=["Phone number"],
            recommended_action="Call within 15 minutes.",
            recommended_response_time_minutes=15,
            confidence=0.9,
        ),
        fallback_used=False,
    )


@pytest.mark.asyncio
async def test_slack_notification_formats_actionable_non_sensitive_content() -> None:
    """Slack receives an actionable summary without the lead's email address."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://hooks.slack.example/services/test"
        assert "New Qualified Lead" in payload["text"]
        assert "maria.santos@example.com" not in payload["text"]
        return httpx.Response(200, request=request)

    notifier = SlackNotifier(
        "https://hooks.slack.example/services/test", 5, 1, httpx.MockTransport(handler)
    )
    result = await notifier.send(_event())

    assert result.success is True
    assert result.provider == "slack"


@pytest.mark.asyncio
async def test_discord_notification_failure_is_returned_not_raised() -> None:
    """A permanent Discord failure can be converted to partial event completion."""
    notifier = DiscordNotifier(
        "https://discord.example/api/webhooks/test",
        5,
        1,
        httpx.MockTransport(lambda request: httpx.Response(400, request=request)),
    )

    result = await notifier.send(_event())

    assert result.success is False
    assert result.provider == "discord"
    assert result.error_message == "Notification provider returned HTTP 400."
