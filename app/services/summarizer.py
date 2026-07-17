"""Provider selection and resilient lead summarization."""

from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings
from app.domain.leads import Lead
from app.providers.base import LeadSummarizerProvider, ProviderError, ProviderResult
from app.providers.mock import MockLeadSummarizerProvider
from app.providers.ollama_provider import create_ollama_provider
from app.providers.openai_compatible import create_openai_compatible_provider
from app.providers.openai_provider import create_openai_provider
from app.services.fallback import create_fallback_summary


@dataclass(frozen=True)
class SummaryOutcome:
    """The final summary plus metadata for every provider attempt."""

    result: ProviderResult
    fallback_used: bool
    attempts: tuple["ProviderAttempt", ...]


@dataclass(frozen=True)
class ProviderAttempt:
    """Metadata for one successful or failed provider attempt."""

    provider: str
    model: str
    success: bool
    fallback_used: bool
    result: ProviderResult | None = None
    latency_ms: int | None = None
    error_message: str | None = None


def select_provider(settings: Settings, provider_name: str | None = None) -> LeadSummarizerProvider:
    """Choose the configured provider currently available in this release."""
    selected_provider = provider_name or settings.llm_provider
    if selected_provider == "mock":
        return MockLeadSummarizerProvider(settings.llm_model)
    try:
        if selected_provider == "openai":
            return create_openai_provider(settings)
        if selected_provider == "ollama":
            return create_ollama_provider(settings)
        if selected_provider == "openai_compatible":
            return create_openai_compatible_provider(settings)
    except ProviderError as exc:
        return UnavailableProvider(selected_provider, settings.llm_model, str(exc))
    return UnavailableProvider(selected_provider, settings.llm_model, "Unsupported LLM provider.")


class LeadSummarizer:
    """Generate a structured summary and protect processing with a fallback."""

    def __init__(
        self,
        provider: LeadSummarizerProvider,
        secondary_provider: LeadSummarizerProvider | None = None,
    ) -> None:
        self._provider = provider
        self._secondary_provider = secondary_provider

    async def summarize(self, lead: Lead) -> SummaryOutcome:
        """Use the configured provider, falling back deterministically on failure."""
        attempts: list[ProviderAttempt] = []
        providers = [self._provider]
        if self._secondary_provider:
            providers.append(self._secondary_provider)
        for provider in providers:
            started_at = perf_counter()
            try:
                result = await provider.summarize(lead)
            except Exception as exc:
                attempts.append(
                    ProviderAttempt(
                        provider=getattr(provider, "provider_name", "unknown"),
                        model=getattr(provider, "model_name", "unknown"),
                        success=False,
                        fallback_used=True,
                        latency_ms=int((perf_counter() - started_at) * 1000),
                        error_message=str(exc)[:500],
                    )
                )
                continue
            attempts.append(
                ProviderAttempt(
                    provider=result.provider,
                    model=result.model,
                    success=True,
                    fallback_used=False,
                    result=result,
                    latency_ms=result.latency_ms,
                )
            )
            return SummaryOutcome(result=result, fallback_used=False, attempts=tuple(attempts))

        fallback_result = create_fallback_summary(lead)
        attempts.append(
            ProviderAttempt(
                provider=fallback_result.provider,
                model=fallback_result.model,
                success=True,
                fallback_used=True,
                result=fallback_result,
                latency_ms=fallback_result.latency_ms,
            )
        )
        return SummaryOutcome(result=fallback_result, fallback_used=True, attempts=tuple(attempts))


class UnavailableProvider:
    """Represent a configured provider that cannot currently be initialized."""

    def __init__(self, provider_name: str, model_name: str, reason: str) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self._reason = reason

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Trigger deterministic fallback while preserving failure metadata."""
        raise ProviderError(self._reason)
