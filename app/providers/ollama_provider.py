"""Ollama local or self-hosted provider implementation."""

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
from app.providers.openai_compatible import SYSTEM_PROMPT, TransientProviderError


class OllamaProvider:
    """Call Ollama's native chat endpoint with JSON-schema output."""

    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: int,
        max_attempts: int,
        input_cost_per_million: float | None,
        output_cost_per_million: float | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._input_cost_per_million = input_cost_per_million
        self._output_cost_per_million = output_cost_per_million
        self._transport = transport

    async def summarize(self, lead: Lead) -> ProviderResult:
        """Request a validated summary, retrying temporary connection failures."""
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
        payload = {
            "model": self.model_name,
            "stream": False,
            "format": LeadSummary.model_json_schema(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(lead.model_dump(mode="json"))},
            ],
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.RequestError as exc:
            raise TransientProviderError("Unable to connect to Ollama.") from exc
        if response.status_code in {429, 502, 503, 504}:
            raise TransientProviderError(f"Ollama returned temporary HTTP {response.status_code}.")
        if response.is_error:
            raise ProviderError(f"Ollama returned HTTP {response.status_code}.")
        try:
            body: dict[str, Any] = response.json()
            summary = LeadSummary.model_validate_json(body["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ProviderError("Ollama returned an invalid structured summary.") from exc
        input_tokens = _as_int(body.get("prompt_eval_count"))
        output_tokens = _as_int(body.get("eval_count"))
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


def create_ollama_provider(settings: Settings) -> OllamaProvider:
    """Create the configured Ollama provider."""
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.max_retry_attempts,
        input_cost_per_million=settings.llm_input_cost_per_million,
        output_cost_per_million=settings.llm_output_cost_per_million,
    )


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
