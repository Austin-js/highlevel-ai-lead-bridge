"""OpenAI Chat Completions-compatible provider implementation."""

import json
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings
from app.domain.leads import Lead
from app.domain.summaries import LeadSummary
from app.providers.base import ProviderError, ProviderResult, estimate_cost_usd

SYSTEM_PROMPT = (
    "You are a lead-intake assistant. Summarize only the supplied lead information. "
    "Do not invent facts. Identify missing information. Return valid JSON matching the required "
    "schema. Keep the output concise and useful to a sales or support team."
)


class TransientProviderError(ProviderError):
    """A retryable provider or network failure."""


class OpenAICompatibleProvider:
    """Call a configurable server implementing the Chat Completions API shape."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: int,
        max_attempts: int,
        input_cost_per_million: float | None,
        output_cost_per_million: float | None,
        provider_name: str = "openai_compatible",
        response_format: dict[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._input_cost_per_million = input_cost_per_million
        self._output_cost_per_million = output_cost_per_million
        self._response_format = response_format or {"type": "json_object"}
        self._transport = transport

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Request JSON output, retrying only temporary failures."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(TransientProviderError),
            wait=wait_exponential_jitter(initial=0.1, max=2),
            stop=stop_after_attempt(self._max_attempts),
            reraise=True,
        ):
            with attempt:
                return await self._request_summary(lead)
        raise ProviderError("Provider retry loop finished without a response.")

    async def _request_summary(self, lead: Lead) -> ProviderResult:
        started_at = perf_counter()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(lead.model_dump(mode="json"))},
            ],
            "response_format": self._response_format,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise TransientProviderError("Unable to connect to the LLM provider.") from exc

        if response.status_code in {429, 502, 503, 504}:
            raise TransientProviderError(
                f"LLM provider returned temporary HTTP {response.status_code}."
            )
        if response.is_error:
            raise ProviderError(f"LLM provider returned HTTP {response.status_code}.")

        try:
            body: dict[str, Any] = response.json()
            content = body["choices"][0]["message"]["content"]
            summary = LeadSummary.model_validate_json(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ProviderError("LLM provider returned an invalid structured summary.") from exc

        usage = body.get("usage", {})
        input_tokens = _as_int(usage.get("prompt_tokens"))
        output_tokens = _as_int(usage.get("completion_tokens"))
        return ProviderResult(
            summary=summary,
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost_usd(
                input_tokens,
                output_tokens,
                self._input_cost_per_million,
                self._output_cost_per_million,
            ),
            latency_ms=int((perf_counter() - started_at) * 1000),
        )


def create_openai_compatible_provider(settings: Settings) -> OpenAICompatibleProvider:
    """Create an OpenAI-compatible provider from application configuration."""
    if not settings.llm_base_url:
        raise ProviderError("LLM_BASE_URL is required for the openai_compatible provider.")
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.max_retry_attempts,
        input_cost_per_million=settings.llm_input_cost_per_million,
        output_cost_per_million=settings.llm_output_cost_per_million,
    )


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
