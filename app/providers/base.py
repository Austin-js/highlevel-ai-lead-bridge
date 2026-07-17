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


def estimate_cost_usd(
    input_tokens: int | None,
    output_tokens: int | None,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
) -> float | None:
    """Calculate configurable token cost, or return unknown when data is incomplete."""
    if (
        input_tokens is None
        or output_tokens is None
        or input_cost_per_million is None
        or output_cost_per_million is None
    ):
        return None
    return (
        input_tokens * input_cost_per_million + output_tokens * output_cost_per_million
    ) / 1_000_000


class LeadSummarizerProvider(Protocol):
    """Interface shared by all hosted and local LLM implementations."""

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Return a Pydantic-validated summary for one lead."""
