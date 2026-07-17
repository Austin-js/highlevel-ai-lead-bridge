"""Slack incoming-webhook notifier."""

from app.domain.processed import ProcessedLeadEvent
from app.services.notifier import WebhookNotifier


class SlackNotifier(WebhookNotifier):
    """Send a formatted lead summary through a Slack incoming webhook."""

    provider_name = "slack"

    def payload(self, event: ProcessedLeadEvent) -> dict[str, str]:
        """Build Slack's simple incoming-webhook payload."""
        return {"text": self.format_event(event)}
