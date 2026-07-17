"""Provider-neutral lead summarization contracts."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.leads import Lead
from app.domain.summaries import LeadSummary


class ProviderError(Exception):
    """A provider could not produce a valid summary."""


@dataclass(frozen=True)
class ProviderResult:
    """A successful structured provider response with usage metadata."""

    summary: LeadSummary
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms: int | None


class LeadSummarizerProvider(Protocol):
    """Interface shared by all hosted and local LLM implementations."""

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Return a Pydantic-validated summary for one lead."""
