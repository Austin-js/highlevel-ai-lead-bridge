"""Deterministic free provider used in demo mode and tests."""

from app.domain.leads import Lead
from app.domain.summaries import LeadSummary, Qualification, Urgency
from app.providers.base import ProviderResult


class MockLeadSummarizerProvider:
    """Produce predictable summaries without a network request or API key."""

    provider_name = "mock"

    def __init__(self, model_name: str = "demo") -> None:
        self.model_name = model_name

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Generate a valid summary from supplied lead fields only."""
        details = lead_details(lead)
        missing = missing_information(lead)
        urgency: Urgency = "high" if lead.service_requested else "medium"
        qualification: Qualification = "high_intent" if lead.service_requested else "uncertain"
        response_time = 15 if urgency == "high" else 60
        overview = f"New lead: {lead.full_name}."
        if lead.service_requested:
            overview = f"{overview} Requested service: {lead.service_requested}."
        return ProviderResult(
            summary=LeadSummary(
                overview=overview,
                intent=lead.service_requested or "General dental inquiry",
                urgency=urgency,
                qualification=qualification,
                key_details=details,
                missing_information=missing,
                recommended_action="Contact the lead and confirm their preferred appointment time.",
                recommended_response_time_minutes=response_time,
                confidence=0.8,
            ),
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=0.0,
            latency_ms=0,
        )


def lead_details(lead: Lead) -> list[str]:
    """List only known operational details."""
    details: list[str] = []
    if lead.service_requested:
        details.append(f"Requested service: {lead.service_requested}")
    if lead.preferred_schedule:
        details.append(f"Preferred schedule: {lead.preferred_schedule}")
    if lead.source:
        details.append(f"Source: {lead.source}")
    if lead.message:
        details.append(f"Message: {lead.message}")
    return details


def missing_information(lead: Lead) -> list[str]:
    """Identify fields that would help staff follow up."""
    missing: list[str] = []
    if not lead.email:
        missing.append("Email address")
    if not lead.phone:
        missing.append("Phone number")
    if not lead.preferred_schedule:
        missing.append("Preferred schedule")
    return missing
