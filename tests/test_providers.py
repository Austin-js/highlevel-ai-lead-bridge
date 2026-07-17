"""Mocked HTTP tests for hosted and local inference providers."""

import json

import httpx
import pytest

from app.domain.leads import Lead
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def _lead() -> Lead:
    return Lead(full_name="Maria Santos", service_requested="Dental implants")


def _summary() -> dict[str, object]:
    return {
        "overview": "Maria requested dental implants.",
        "intent": "Dental implants",
        "urgency": "high",
        "qualification": "high_intent",
        "key_details": ["Requested service: Dental implants"],
        "missing_information": ["Preferred schedule"],
        "recommended_action": "Call within 15 minutes.",
        "recommended_response_time_minutes": 15,
        "confidence": 0.9,
    }


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_usage_and_retries_temporary_failure() -> None:
    """A 503 is retried and a valid structured response is recorded."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": json.dumps(_summary())}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://llm.example.com/v1",
        api_key="test-key",
        model="test-model",
        timeout_seconds=5,
        max_attempts=2,
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
        transport=httpx.MockTransport(handler),
    )

    result = await provider.summarize(_lead())

    assert calls == 2
    assert result.provider == "openai_compatible"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.estimated_cost_usd == 0.00002


@pytest.mark.asyncio
async def test_ollama_provider_uses_native_chat_schema() -> None:
    """Ollama responses are validated without needing a running local server."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"]["title"] == "LeadSummary"
        return httpx.Response(
            200,
            request=request,
            json={
                "message": {"content": json.dumps(_summary())},
                "prompt_eval_count": 7,
                "eval_count": 3,
            },
        )

    provider = OllamaProvider(
        base_url="http://ollama.example.com",
        model="local-model",
        timeout_seconds=5,
        max_attempts=1,
        input_cost_per_million=None,
        output_cost_per_million=None,
        transport=httpx.MockTransport(handler),
    )

    result = await provider.summarize(_lead())

    assert result.provider == "ollama"
    assert result.model == "local-model"
    assert result.estimated_cost_usd is None
