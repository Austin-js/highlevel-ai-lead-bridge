"""Small isolated client for supported HighLevel contact updates."""

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class HighLevelError(Exception):
    """A non-retryable HighLevel API operation error."""


class TransientHighLevelError(HighLevelError):
    """A temporary HighLevel or network failure eligible for retry."""


class HighLevelClient:
    """Perform contact notes, tag, and custom-field operations through the v3 API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: int,
        max_attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._transport = transport

    async def add_note(self, contact_id: str, body: str) -> None:
        """Add a text note to a contact."""
        await self._request("POST", f"/contacts/{contact_id}/notes", {"body": body})

    async def add_tags(self, contact_id: str, tags: list[str]) -> None:
        """Add one or more tags to a contact."""
        await self._request("POST", f"/contacts/{contact_id}/tags", {"tags": tags})

    async def update_custom_field(self, contact_id: str, field_id: str, value: str) -> None:
        """Update a custom field by its configured HighLevel field id."""
        await self._request(
            "PUT",
            f"/contacts/{contact_id}",
            {"customFields": [{"id": field_id, "value": value}]},
        )

    async def _request(self, method: str, path: str, payload: dict[str, Any]) -> None:
        """Issue one authenticated request with bounded temporary retries."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(TransientHighLevelError),
            wait=wait_exponential_jitter(initial=0.1, max=2),
            stop=stop_after_attempt(self._max_attempts),
            reraise=True,
        ):
            with attempt:
                await self._send(method, path, payload)
                return

    async def _send(self, method: str, path: str, payload: dict[str, Any]) -> None:
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Version": "2021-07-28",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise TransientHighLevelError("Unable to connect to HighLevel.") from exc
        if response.status_code in {429, 502, 503, 504}:
            raise TransientHighLevelError(
                f"HighLevel returned temporary HTTP {response.status_code}."
            )
        if response.is_error:
            raise HighLevelError(f"HighLevel returned HTTP {response.status_code}.")
