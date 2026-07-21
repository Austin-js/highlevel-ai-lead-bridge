"""Authenticated operational inspection and replay of persisted lead events."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EventRecord
from app.db.repositories import create_dead_letter, get_event_by_external_id
from app.domain.events import AdminEventDetail, ReplayReceipt
from app.domain.leads import Lead
from app.services.event_processor import EventProcessor, ProcessingOutcome

logger = logging.getLogger(__name__)


class EventNotFoundError(Exception):
    """Raised when an administrative request references no persisted event."""


class EventReplayService:
    """Inspect events and recover incomplete work without accepting a new webhook."""

    def __init__(self, session: AsyncSession, processor: EventProcessor | None = None) -> None:
        self._session = session
        self._processor = processor or EventProcessor(session)

    async def get_detail(self, event_id: str) -> AdminEventDetail:
        """Return a safe status view for an event id."""
        event = await self._get_event(event_id)
        return _event_detail(event)

    async def replay(self, event_id: str) -> ReplayReceipt:
        """Reprocess an event or place it in the dead-letter table once attempts are exhausted."""
        event = await self._get_event(event_id)
        max_attempts = get_settings().max_event_replay_attempts
        if event.attempt_count >= max_attempts:
            await self._dead_letter(event, "Maximum event replay attempts reached.")
            return _replay_receipt(event, ["Event moved to dead-letter tracking."])

        logger.info("event_replay_requested", extra={"event_id": event.external_event_id})
        lead = Lead.model_validate(event.normalized_payload)
        try:
            outcome = await self._processor.process(event, lead)
        except Exception:
            await self._session.rollback()
            event = await self._get_event(event_id)
            event.status = "failed"
            event.error_message = "Processing failed; inspect application logs."
            await self._session.commit()
            if event.attempt_count >= max_attempts:
                await self._dead_letter(event, event.error_message)
            logger.error("event_replay_failed", extra={"event_id": event.external_event_id})
            return _replay_receipt(event, [event.error_message])

        warnings = _outcome_warnings(outcome)
        if event.status == "partially_completed" and event.attempt_count >= max_attempts:
            await self._dead_letter(
                event, "Maximum event replay attempts reached with partial completion."
            )
            warnings.append("Event moved to dead-letter tracking.")
        logger.info("event_replayed", extra={"event_id": event.external_event_id})
        return _replay_receipt(event, warnings)

    async def _get_event(self, event_id: str) -> EventRecord:
        event = await get_event_by_external_id(self._session, event_id)
        if not event:
            raise EventNotFoundError
        return event

    async def _dead_letter(self, event: EventRecord, reason: str) -> None:
        event.status = "dead_lettered"
        event.error_message = reason
        await create_dead_letter(self._session, event, reason)
        await self._session.commit()
        logger.warning("event_dead_lettered", extra={"event_id": event.external_event_id})


def _event_detail(event: EventRecord) -> AdminEventDetail:
    return AdminEventDetail(
        event_id=event.external_event_id,
        event_type=event.event_type,
        contact_id=event.contact_id,
        status=event.status,
        attempt_count=event.attempt_count,
        error_message=event.error_message,
        dead_lettered=event.status == "dead_lettered",
    )


def _replay_receipt(event: EventRecord, warnings: list[str]) -> ReplayReceipt:
    return ReplayReceipt(
        status=event.status,
        event_id=event.external_event_id,
        attempt_count=event.attempt_count,
        dead_lettered=event.status == "dead_lettered",
        warnings=warnings or None,
    )


def _outcome_warnings(outcome: ProcessingOutcome) -> list[str]:
    warnings = list(outcome.highlevel_sync.warnings)
    if not outcome.notification.success:
        warnings.insert(0, outcome.notification.error_message or "Notification delivery failed.")
    return warnings
