"""Persistence operations for received events."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeadLetterRecord, EventRecord


async def find_duplicate_event(
    session: AsyncSession, external_event_id: str, payload_hash: str
) -> EventRecord | None:
    """Find an event already received through either idempotency key."""
    result = await session.execute(
        select(EventRecord).where(
            or_(
                EventRecord.external_event_id == external_event_id,
                EventRecord.payload_hash == payload_hash,
            )
        )
    )
    return result.scalar_one_or_none()


async def create_event(session: AsyncSession, event: EventRecord) -> EventRecord:
    """Store a newly accepted event."""
    session.add(event)
    await session.flush()
    return event


async def get_event_by_external_id(session: AsyncSession, event_id: str) -> EventRecord | None:
    """Retrieve an event for authenticated operational inspection or replay."""
    result = await session.execute(
        select(EventRecord).where(EventRecord.external_event_id == event_id)
    )
    return result.scalar_one_or_none()


async def create_dead_letter(
    session: AsyncSession, event: EventRecord, reason: str
) -> DeadLetterRecord:
    """Record that an event exhausted processing or replay attempts."""
    existing = await session.scalar(
        select(DeadLetterRecord).where(DeadLetterRecord.event_id == event.id)
    )
    if existing:
        return existing
    dead_letter = DeadLetterRecord(
        event_id=event.id,
        external_event_id=event.external_event_id,
        reason=reason,
        replay_attempts=event.attempt_count,
    )
    session.add(dead_letter)
    await session.flush()
    return dead_letter
