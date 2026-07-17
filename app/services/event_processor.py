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
        self._summarizer = summarizer or LeadSummarizer(select_provider(get_settings()))

    async def process(self, event: EventRecord, lead: Lead) -> SummaryOutcome:
        """Summarize a persisted event and mark its processing lifecycle complete."""
        event.status = "processing"
        event.attempt_count += 1
        event.processing_started_at = datetime.now(UTC)
        await self._session.commit()

        outcome = await self._summarizer.summarize(lead)
        if outcome.fallback_used:
            self._session.add(
                InferenceRecord(
                    event_id=event.id,
                    provider=outcome.failed_provider or "unknown",
                    model=outcome.failed_model or "unknown",
                    latency_ms=outcome.failed_latency_ms,
                    success=False,
                    fallback_used=True,
                    error_message=outcome.provider_error,
                )
            )

        result = outcome.result
        self._session.add(
            InferenceRecord(
                event_id=event.id,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                estimated_cost_usd=result.estimated_cost_usd,
                latency_ms=result.latency_ms,
                success=True,
                fallback_used=outcome.fallback_used,
            )
        )
        event.status = "completed"
        event.processed_at = datetime.now(UTC)
        await self._session.commit()
        return outcome
