"""Unit tests for replay and dead-letter orchestration."""

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.db.models import EventRecord
from app.domain.leads import Lead
from app.services import event_replay
from app.services.event_replay import EventReplayService


class FakeSession:
    """Minimal async session double for replay orchestration tests."""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class SuccessfulProcessor:
    """Processor double that completes a replay without external integrations."""

    async def process(self, event: EventRecord, lead: Lead) -> SimpleNamespace:
        event.attempt_count += 1
        event.status = "completed"
        return SimpleNamespace(
            notification=SimpleNamespace(success=True, error_message=None),
            highlevel_sync=SimpleNamespace(warnings=[]),
        )


def _event(attempt_count: int = 1) -> EventRecord:
    return EventRecord(
        id=1,
        external_event_id="evt_replay_unit",
        event_type="contact.created",
        contact_id="contact_unit",
        payload_hash="a" * 64,
        raw_payload={},
        normalized_payload=Lead(contact_id="contact_unit", full_name="Maria Santos").model_dump(
            mode="json"
        ),
        status="partially_completed",
        attempt_count=attempt_count,
    )


@pytest.mark.asyncio
async def test_replay_service_reprocesses_the_original_normalized_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replay uses persisted normalized data and increments the event attempt count."""
    event = _event()

    async def get_event(*_: object) -> EventRecord:
        return event

    monkeypatch.setattr(event_replay, "get_event_by_external_id", get_event)
    receipt = await EventReplayService(FakeSession(), SuccessfulProcessor()).replay(
        event.external_event_id
    )

    assert receipt.status == "completed"
    assert receipt.attempt_count == 2
    assert receipt.dead_lettered is False


@pytest.mark.asyncio
async def test_replay_service_dead_letters_exhausted_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exhausted replay budget transitions the event before processing starts."""
    event = _event(attempt_count=1)
    monkeypatch.setenv("MAX_EVENT_REPLAY_ATTEMPTS", "1")
    get_settings.cache_clear()

    async def get_event(*_: object) -> EventRecord:
        return event

    async def create_dead_letter(*_: object) -> None:
        return None

    monkeypatch.setattr(event_replay, "get_event_by_external_id", get_event)
    monkeypatch.setattr(event_replay, "create_dead_letter", create_dead_letter)
    receipt = await EventReplayService(FakeSession(), SuccessfulProcessor()).replay(
        event.external_event_id
    )
    get_settings.cache_clear()

    assert receipt.status == "dead_lettered"
    assert receipt.dead_lettered is True
    assert receipt.warnings == ["Event moved to dead-letter tracking."]
