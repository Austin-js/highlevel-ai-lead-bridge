"""Provider selection and resilient lead summarization."""

from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings
from app.domain.leads import Lead
from app.providers.base import LeadSummarizerProvider, ProviderError, ProviderResult
from app.providers.mock import MockLeadSummarizerProvider
from app.services.fallback import create_fallback_summary


@dataclass(frozen=True)
class SummaryOutcome:
    """The final summary plus metadata for every provider attempt."""

    result: ProviderResult
    fallback_used: bool
    failed_provider: str | None = None
    failed_model: str | None = None
    failed_latency_ms: int | None = None
    provider_error: str | None = None


def select_provider(settings: Settings) -> LeadSummarizerProvider:
    """Choose the configured provider currently available in this release."""
    if settings.llm_provider == "mock":
        return MockLeadSummarizerProvider(settings.llm_model)
    return UnavailableProvider(settings.llm_provider, settings.llm_model)


class UnavailableProvider:
    """Represent a configured provider that will be added in a later phase."""

    def __init__(self, provider_name: str, model_name: str) -> None:
        self.provider_name = provider_name
        self.model_name = model_name

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Trigger the deterministic fallback while preserving attempt metadata."""
        raise ProviderError(f"LLM provider '{self.provider_name}' is not configured.")


class LeadSummarizer:
    """Generate a structured summary and protect processing with a fallback."""

    def __init__(self, provider: LeadSummarizerProvider) -> None:
        self._provider = provider

    async def summarize(self, lead: Lead) -> SummaryOutcome:
        """Use the configured provider, falling back deterministically on failure."""
        started_at = perf_counter()
        try:
            result = await self._provider.summarize(lead)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            return SummaryOutcome(
                result=create_fallback_summary(lead),
                fallback_used=True,
                failed_provider=getattr(self._provider, "provider_name", "unknown"),
                failed_model=getattr(self._provider, "model_name", "unknown"),
                failed_latency_ms=elapsed_ms,
                provider_error=str(exc)[:500],
            )
        return SummaryOutcome(result=result, fallback_used=False)
