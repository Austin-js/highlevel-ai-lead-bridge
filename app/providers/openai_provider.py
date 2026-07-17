"""OpenAI-hosted provider configuration."""

from app.core.config import Settings
from app.domain.summaries import LeadSummary
from app.providers.base import ProviderError
from app.providers.openai_compatible import OpenAICompatibleProvider

OPENAI_BASE_URL = "https://api.openai.com/v1"


def create_openai_provider(settings: Settings) -> OpenAICompatibleProvider:
    """Create the official OpenAI adapter with schema-constrained JSON output."""
    if not settings.openai_api_key:
        raise ProviderError("OPENAI_API_KEY is required for the openai provider.")
    return OpenAICompatibleProvider(
        base_url=OPENAI_BASE_URL,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.max_retry_attempts,
        input_cost_per_million=settings.llm_input_cost_per_million,
        output_cost_per_million=settings.llm_output_cost_per_million,
        provider_name="openai",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "lead_summary",
                "strict": True,
                "schema": LeadSummary.model_json_schema(),
            },
        },
    )
