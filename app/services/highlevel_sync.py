"""Optional, isolated HighLevel contact synchronization workflow."""

from dataclasses import dataclass
from typing import Protocol

from app.clients.highlevel import HighLevelClient, HighLevelError
from app.core.config import Settings
from app.domain.processed import ProcessedLeadEvent


@dataclass(frozen=True)
class HighLevelSyncResult:
    """Synchronization success state and independently collected operation warnings."""

    success: bool
    warnings: list[str]


class HighLevelSync(Protocol):
    """Contract for HighLevel synchronization implementations."""

    async def sync(self, event: ProcessedLeadEvent) -> HighLevelSyncResult:
        """Synchronize selected summary data to the lead's CRM contact."""


class NullHighLevelSync:
    """No-op sync used whenever the optional integration is disabled."""

    async def sync(self, event: ProcessedLeadEvent) -> HighLevelSyncResult:
        """Report a successful intentional no-op."""
        return HighLevelSyncResult(success=True, warnings=[])


class HighLevelContactSync:
    """Add a summary note, operational tags, and optional recommended-action field."""

    def __init__(
        self,
        client: HighLevelClient,
        summary_tag: str | None,
        high_intent_tag: str | None,
        recommended_action_field_id: str | None,
    ) -> None:
        self._client = client
        self._summary_tag = summary_tag
        self._high_intent_tag = high_intent_tag
        self._recommended_action_field_id = recommended_action_field_id

    async def sync(self, event: ProcessedLeadEvent) -> HighLevelSyncResult:
        """Attempt each configured operation without invalidating the lead summary."""
        contact_id = event.lead.contact_id
        if not contact_id:
            return HighLevelSyncResult(
                success=False, warnings=["HighLevel contact id is unavailable."]
            )

        warnings: list[str] = []
        try:
            await self._client.add_note(contact_id, _summary_note(event))
        except HighLevelError:
            warnings.append("HighLevel contact note could not be created.")

        tags = [tag for tag in [self._summary_tag] if tag]
        if event.summary.qualification == "high_intent" and self._high_intent_tag:
            tags.append(self._high_intent_tag)
        if tags:
            try:
                await self._client.add_tags(contact_id, tags)
            except HighLevelError:
                warnings.append("HighLevel contact tags could not be added.")

        if self._recommended_action_field_id:
            try:
                await self._client.update_custom_field(
                    contact_id,
                    self._recommended_action_field_id,
                    event.summary.recommended_action,
                )
            except HighLevelError:
                warnings.append("HighLevel recommended-action field could not be updated.")
        return HighLevelSyncResult(success=not warnings, warnings=warnings)


def select_highlevel_sync(settings: Settings) -> HighLevelSync:
    """Create optional HighLevel sync only when it is explicitly enabled and configured."""
    if not settings.highlevel_sync_enabled:
        return NullHighLevelSync()
    if not settings.highlevel_api_token:
        return MisconfiguredHighLevelSync("HIGHLEVEL_API_TOKEN is not configured.")
    return HighLevelContactSync(
        HighLevelClient(
            base_url=settings.highlevel_api_base_url,
            api_token=settings.highlevel_api_token,
            timeout_seconds=settings.http_timeout_seconds,
            max_attempts=settings.max_retry_attempts,
        ),
        settings.highlevel_summary_tag,
        settings.highlevel_high_intent_tag,
        settings.highlevel_recommended_action_field_id,
    )


class MisconfiguredHighLevelSync:
    """Surface missing integration configuration as a safe partial-completion result."""

    def __init__(self, message: str) -> None:
        self._message = message

    async def sync(self, event: ProcessedLeadEvent) -> HighLevelSyncResult:
        """Do not raise integration setup errors into the webhook response."""
        return HighLevelSyncResult(success=False, warnings=[self._message])


def _summary_note(event: ProcessedLeadEvent) -> str:
    """Render a concise CRM note without the original raw webhook payload."""
    summary = event.summary
    return "\n".join(
        [
            "AI Lead Summary",
            f"Overview: {summary.overview}",
            f"Urgency: {summary.urgency}",
            f"Qualification: {summary.qualification}",
            f"Recommended action: {summary.recommended_action}",
        ]
    )
