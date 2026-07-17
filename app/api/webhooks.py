"""HighLevel webhook intake endpoint."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_webhook_secret
from app.db.models import EventRecord
from app.db.repositories import create_event, find_duplicate_event
from app.db.session import get_db_session
from app.domain.events import HighLevelEventPayload, WebhookReceipt
from app.services.event_processor import EventProcessor
from app.services.lead_normalizer import derive_event_id, normalize_lead, stable_payload_hash

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/highlevel",
    response_model=WebhookReceipt,
    response_model_exclude_none=True,
    dependencies=[Depends(verify_webhook_secret)],
)
async def receive_highlevel_webhook(
    payload: HighLevelEventPayload,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> WebhookReceipt:
    """Authenticate, validate, normalize, persist, and deduplicate an inbound event."""
    lead = normalize_lead(payload)
    raw_payload = await request.json()
    payload_hash = stable_payload_hash(raw_payload)
    event_id = derive_event_id(payload, lead)

    if await find_duplicate_event(session, event_id, payload_hash):
        return WebhookReceipt(status="duplicate", event_id=event_id, duplicate=True)

    event = EventRecord(
        external_event_id=event_id,
        event_type=payload.event_type,
        contact_id=lead.contact_id,
        payload_hash=payload_hash,
        raw_payload=raw_payload,
        normalized_payload=lead.model_dump(mode="json"),
        status="received",
    )
    try:
        await create_event(session, event)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return WebhookReceipt(status="duplicate", event_id=event_id, duplicate=True)

    outcome = await EventProcessor(session).process(event, lead)
    warnings = (
        [outcome.notification.error_message or "Notification delivery failed."]
        if not outcome.notification.success
        else None
    )
    return WebhookReceipt(
        status="completed" if outcome.notification.success else "partially_completed",
        event_id=event_id,
        duplicate=False,
        fallback_used=outcome.summary.fallback_used,
        warnings=warnings,
    )
