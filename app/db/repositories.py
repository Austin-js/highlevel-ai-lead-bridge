"""Persistence operations for received events."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventRecord


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
