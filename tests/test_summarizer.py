"""Unit tests for structured summaries and deterministic fallback behavior."""

import pytest

from app.domain.leads import Lead
from app.domain.summaries import LeadSummary
from app.providers.base import ProviderError, ProviderResult
from app.providers.mock import MockLeadSummarizerProvider
from app.services.summarizer import LeadSummarizer


def _lead() -> Lead:
    return Lead(
        contact_id="contact_demo_001",
        first_name="Maria",
        last_name="Santos",
        full_name="Maria Santos",
        phone="+639171234567",
        source="Facebook Ads",
        service_requested="Dental implants",
        preferred_schedule="Saturday morning",
        message="I would like to ask about installment options.",
    )


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_structured_summary() -> None:
    """Demo mode remains usable with no external LLM credentials."""
    result = await MockLeadSummarizerProvider().summarize(_lead())

    assert result.provider == "mock"
    assert result.summary.qualification == "high_intent"
    assert "Requested service: Dental implants" in result.summary.key_details


class FailingProvider:
    """A test double that simulates provider unavailability."""

    provider_name = "failing"
    model_name = "unavailable"

    async def summarize(self, lead: Lead) -> ProviderResult:
        raise ProviderError("Connection timed out")


@pytest.mark.asyncio
async def test_provider_failure_uses_deterministic_fallback() -> None:
    """Provider outages do not prevent useful lead processing."""
    outcome = await LeadSummarizer(FailingProvider()).summarize(_lead())

    assert outcome.fallback_used is True
    assert outcome.result.provider == "deterministic_fallback"
    assert outcome.result.summary.overview.startswith("New lead: Maria Santos.")


def test_lead_summary_rejects_invalid_constrained_values() -> None:
    """Provider output cannot use values outside the public summary contract."""
    with pytest.raises(ValueError, match="urgency"):
        LeadSummary(
            overview="A summary",
            intent="An inquiry",
            urgency="immediate",
            qualification="qualified",
            recommended_action="Call the lead.",
            confidence=0.8,
        )
