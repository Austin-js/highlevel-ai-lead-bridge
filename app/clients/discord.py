"""Discord webhook notifier."""

from app.domain.processed import ProcessedLeadEvent
from app.services.notifier import WebhookNotifier


class DiscordNotifier(WebhookNotifier):
    """Send a formatted lead summary through a Discord webhook."""

    provider_name = "discord"

    def payload(self, event: ProcessedLeadEvent) -> dict[str, str]:
        """Build Discord's simple webhook payload."""
        return {"content": self.format_event(event)}
