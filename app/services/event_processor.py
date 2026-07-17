"""Synchronous event-processing workflow."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EventRecord, InferenceRecord
from app.domain.leads import Lead
from app.domain.processed import ProcessedLeadEvent
from app.services.highlevel_sync import HighLevelSync, HighLevelSyncResult, select_highlevel_sync
from app.services.notifier import NotificationResult, Notifier, select_notifier
from app.services.summarizer import LeadSummarizer, SummaryOutcome, select_provider


class ProcessingOutcome:
    """The summary and downstream notification outcomes for one event."""

    def __init__(
        self,
        summary: SummaryOutcome,
        notification: NotificationResult,
        highlevel_sync: HighLevelSyncResult,
    ) -> None:
        self.summary = summary
        self.notification = notification
        self.highlevel_sync = highlevel_sync


class EventProcessor:
    """Run summary generation and persist resulting provider metadata."""

    def __init__(
        self,
        session: AsyncSession,
        summarizer: LeadSummarizer | None = None,
        notifier: Notifier | None = None,
        highlevel_sync: HighLevelSync | None = None,
    ) -> None:
        self._session = session
        settings = get_settings()
        secondary_provider = (
            select_provider(settings, settings.llm_secondary_provider)
            if settings.llm_secondary_provider
            else None
        )
        self._summarizer = summarizer or LeadSummarizer(
            select_provider(settings), secondary_provider
        )
        self._notifier = notifier or select_notifier(settings)
        self._highlevel_sync = highlevel_sync or select_highlevel_sync(settings)

    async def process(self, event: EventRecord, lead: Lead) -> ProcessingOutcome:
        """Summarize a persisted event and mark its processing lifecycle complete."""
        event.status = "processing"
        event.attempt_count += 1
        event.processing_started_at = datetime.now(UTC)
        await self._session.commit()

        outcome = await self._summarizer.summarize(lead)
        for attempt in outcome.attempts:
            self._session.add(
                InferenceRecord(
                    event_id=event.id,
                    provider=attempt.provider,
                    model=attempt.model,
                    input_tokens=attempt.result.input_tokens if attempt.result else None,
                    output_tokens=attempt.result.output_tokens if attempt.result else None,
                    estimated_cost_usd=(
                        attempt.result.estimated_cost_usd if attempt.result else None
                    ),
                    latency_ms=attempt.latency_ms,
                    success=attempt.success,
                    fallback_used=attempt.fallback_used,
                    error_message=attempt.error_message,
                )
            )
        processed_event = ProcessedLeadEvent(
            event_id=event.external_event_id,
            lead=lead,
            summary=outcome.result.summary,
            fallback_used=outcome.fallback_used,
        )
        notification = await self._notifier.send(processed_event)
        highlevel_sync = await self._highlevel_sync.sync(processed_event)
        if notification.success and highlevel_sync.success:
            event.status = "completed"
        else:
            event.status = "partially_completed"
            errors = [
                f"{notification.provider}: {notification.error_message}"
                if not notification.success
                else None,
                *highlevel_sync.warnings,
            ]
            event.error_message = "; ".join(error for error in errors if error)
        event.processed_at = datetime.now(UTC)
        await self._session.commit()
        return ProcessingOutcome(
            summary=outcome,
            notification=notification,
            highlevel_sync=highlevel_sync,
        )
