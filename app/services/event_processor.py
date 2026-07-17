"""Synchronous event-processing workflow."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EventRecord, InferenceRecord
from app.domain.leads import Lead
from app.services.summarizer import LeadSummarizer, SummaryOutcome, select_provider


class EventProcessor:
    """Run summary generation and persist resulting provider metadata."""

    def __init__(self, session: AsyncSession, summarizer: LeadSummarizer | None = None) -> None:
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

    async def process(self, event: EventRecord, lead: Lead) -> SummaryOutcome:
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
        event.status = "completed"
        event.processed_at = datetime.now(UTC)
        await self._session.commit()
        return outcome
