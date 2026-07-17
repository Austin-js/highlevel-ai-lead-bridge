"""Notification formatting, provider selection, and resilient webhook delivery."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings
from app.domain.processed import ProcessedLeadEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationResult:
    """The outcome of one notification attempt."""

    provider: str
    success: bool
    preview: bool = False
    error_message: str | None = None


class Notifier(Protocol):
    """Contract for replaceable downstream notification services."""

    async def send(self, event: ProcessedLeadEvent) -> NotificationResult:
        """Deliver or preview a processed lead event."""


class TransientNotificationError(Exception):
    """A notification failure safe to retry."""


class WebhookNotifier:
    """Common transport and formatting logic for webhook-based notifiers."""

    provider_name = "webhook"

    def __init__(
        self,
        webhook_url: str,
        timeout_seconds: int,
        max_attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._transport = transport

    async def send(self, event: ProcessedLeadEvent) -> NotificationResult:
        """Deliver a formatted webhook payload with bounded temporary retries."""
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(TransientNotificationError),
                wait=wait_exponential_jitter(initial=0.1, max=2),
                stop=stop_after_attempt(self._max_attempts),
                reraise=True,
            ):
                with attempt:
                    await self._post(event)
            return NotificationResult(provider=self.provider_name, success=True)
        except Exception as exc:
            return NotificationResult(
                provider=self.provider_name,
                success=False,
                error_message=str(exc)[:500],
            )

    async def _post(self, event: ProcessedLeadEvent) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(self._webhook_url, json=self.payload(event))
        except httpx.RequestError as exc:
            raise TransientNotificationError("Unable to connect to notification provider.") from exc
        if response.status_code in {429, 502, 503, 504}:
            raise TransientNotificationError(
                f"Notification provider returned temporary HTTP {response.status_code}."
            )
        if response.is_error:
            raise RuntimeError(f"Notification provider returned HTTP {response.status_code}.")

    def payload(self, event: ProcessedLeadEvent) -> dict[str, str]:
        """Return the provider-specific JSON payload."""
        raise NotImplementedError

    @staticmethod
    def format_event(event: ProcessedLeadEvent) -> str:
        """Format a readable notification without exposing the full raw payload."""
        lead = event.lead
        summary = event.summary
        lines = [
            "New Qualified Lead",
            "",
            f"Name: {lead.full_name}",
            f"Service: {lead.service_requested or 'Not provided'}",
            f"Preferred schedule: {lead.preferred_schedule or 'Not provided'}",
            f"Source: {lead.source or 'Not provided'}",
            "",
            "Overview:",
            summary.overview,
            "",
            f"Urgency: {summary.urgency.replace('_', ' ').title()}",
            f"Qualification: {summary.qualification.replace('_', ' ').title()}",
            "",
            "Recommended action:",
            summary.recommended_action,
        ]
        if summary.recommended_response_time_minutes:
            lines.append(
                f"Recommended response time: {summary.recommended_response_time_minutes} minutes"
            )
        if summary.key_details:
            lines.extend(["", "Key details:", *[f"- {item}" for item in summary.key_details]])
        if summary.missing_information:
            lines.extend(
                ["", "Missing information:", *[f"- {item}" for item in summary.missing_information]]
            )
        if event.fallback_used:
            lines.extend(["", "Note: Deterministic fallback summary used."])
        return "\n".join(lines)


class NullNotifier:
    """Represent an intentionally disabled notification integration."""

    async def send(self, event: ProcessedLeadEvent) -> NotificationResult:
        """Report successful no-op delivery."""
        return NotificationResult(provider="none", success=True)


class PreviewNotifier:
    """Log notification previews for local demo use without an external request."""

    async def send(self, event: ProcessedLeadEvent) -> NotificationResult:
        """Write a safe formatted preview to structured logs."""
        logger.info("notification_preview", extra={"event_id": event.event_id})
        logger.debug(WebhookNotifier.format_event(event))
        return NotificationResult(provider="preview", success=True, preview=True)


def select_notifier(settings: Settings) -> Notifier:
    """Create the configured notifier, keeping demo mode free of outbound calls."""
    if settings.app_env == "demo":
        return PreviewNotifier()
    if settings.notification_provider == "none":
        return NullNotifier()
    provider_config = {
        "slack": (settings.slack_webhook_url, "Slack"),
        "discord": (settings.discord_webhook_url, "Discord"),
    }
    webhook_config = provider_config.get(settings.notification_provider)
    if not webhook_config:
        return FailingNotifier("Unsupported notification provider.")
    webhook_url, provider_label = webhook_config
    if not webhook_url:
        return FailingNotifier(f"{provider_label} webhook URL is not configured.")
    common_args = (webhook_url, settings.http_timeout_seconds, settings.max_retry_attempts)
    if settings.notification_provider == "slack":
        from app.clients.slack import SlackNotifier

        return SlackNotifier(*common_args)
    from app.clients.discord import DiscordNotifier

    return DiscordNotifier(*common_args)


class FailingNotifier:
    """Return a controlled failure for invalid notifier configuration."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def send(self, event: ProcessedLeadEvent) -> NotificationResult:
        """Keep notification misconfiguration from crashing webhook processing."""
        return NotificationResult(provider="unavailable", success=False, error_message=self._reason)
