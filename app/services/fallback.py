"""Deterministic summary fallback used when every provider is unavailable."""

from app.domain.leads import Lead
from app.domain.summaries import LeadSummary
from app.providers.base import ProviderResult
from app.providers.mock import lead_details, missing_information


def create_fallback_summary(lead: Lead) -> ProviderResult:
    """Build a useful no-AI summary using only known lead fields."""
    overview_parts = [f"New lead: {lead.full_name}."]
    if lead.service_requested:
        overview_parts.append(f"Requested service: {lead.service_requested}.")
    if lead.preferred_schedule:
        overview_parts.append(f"Preferred schedule: {lead.preferred_schedule}.")
    return ProviderResult(
        summary=LeadSummary(
            overview=" ".join(overview_parts),
            intent=lead.service_requested or "General dental inquiry",
            urgency="medium",
            qualification="uncertain",
            key_details=lead_details(lead),
            missing_information=missing_information(lead),
            recommended_action=(
                "Review the lead details and follow up with the next available staff member."
            ),
            recommended_response_time_minutes=60,
            confidence=1.0,
        ),
        provider="deterministic_fallback",
        model="rules-v1",
        input_tokens=None,
        output_tokens=None,
        estimated_cost_usd=0.0,
        latency_ms=0,
    )
