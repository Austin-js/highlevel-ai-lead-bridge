"""Administrative event inspection and replay endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_secret
from app.db.session import get_db_session
from app.domain.events import AdminEventDetail, ReplayReceipt
from app.services.event_replay import EventNotFoundError, EventReplayService

router = APIRouter(prefix="/admin/events", tags=["admin"])


@router.get(
    "/{event_id}", response_model=AdminEventDetail, dependencies=[Depends(verify_admin_secret)]
)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AdminEventDetail:
    """Inspect an event's status without exposing its raw personal data."""
    try:
        return await EventReplayService(session).get_detail(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found."
        ) from exc


@router.post(
    "/{event_id}/replay",
    response_model=ReplayReceipt,
    response_model_exclude_none=True,
    dependencies=[Depends(verify_admin_secret)],
)
async def replay_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ReplayReceipt:
    """Replay persisted lead processing using the original normalized lead data."""
    try:
        return await EventReplayService(session).replay(event_id)
    except EventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found."
        ) from exc
