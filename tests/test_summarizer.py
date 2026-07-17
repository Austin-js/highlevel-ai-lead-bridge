"""Unit tests for structured summaries and deterministic fallback behavior."""

import pytest

from app.core.config import Settings
from app.domain.leads import Lead
from app.domain.summaries import LeadSummary
from app.providers.base import ProviderError, ProviderResult
from app.providers.mock import MockLeadSummarizerProvider
from app.services.summarizer import LeadSummarizer, select_provider


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


def test_provider_selection_supports_configured_provider_types() -> None:
    """Configured adapters are selected without making any outbound request."""
    openai = select_provider(
        Settings(llm_provider="openai", llm_model="test", openai_api_key="test-key")
    )
    ollama = select_provider(Settings(llm_provider="ollama", llm_model="test"))
    compatible = select_provider(
        Settings(
            llm_provider="openai_compatible",
            llm_model="test",
            llm_base_url="http://llm.example.com/v1",
        )
    )

    assert openai.provider_name == "openai"
    assert ollama.provider_name == "ollama"
    assert compatible.provider_name == "openai_compatible"
