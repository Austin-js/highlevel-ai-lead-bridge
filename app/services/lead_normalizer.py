"""Lead cleaning and stable idempotency key generation."""

import hashlib
import json
from typing import Any

from app.domain.events import HighLevelEventPayload
from app.domain.leads import Lead


def _clean(value: object) -> str | None:
    """Trim and collapse whitespace, converting empty values to None."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def normalize_lead(payload: HighLevelEventPayload) -> Lead:
    """Normalize an incoming contact without requiring email or phone fields."""
    contact = payload.contact
    first_name = _clean(contact.first_name)
    last_name = _clean(contact.last_name)
    phone = _clean(contact.phone)
    full_name = " ".join(part for part in (first_name, last_name) if part) or "Unknown lead"
    custom_fields = {
        key: value
        for key, value in contact.custom_fields.items()
        if not isinstance(value, str) or _clean(value) is not None
    }
    return Lead(
        contact_id=_clean(contact.id),
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        email=_clean(contact.email),
        phone="".join(phone.split()) if phone else None,
        source=_clean(contact.source),
        service_requested=_clean(custom_fields.get("service_requested")),
        preferred_schedule=_clean(custom_fields.get("preferred_schedule")),
        message=_clean(custom_fields.get("message")),
        location_id=_clean(payload.location_id),
        custom_fields=custom_fields,
    )


def stable_payload_hash(payload: dict[str, Any]) -> str:
    """Create a deterministic SHA-256 hash from canonical JSON data."""
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def derive_event_id(payload: HighLevelEventPayload, lead: Lead) -> str:
    """Use the sender id when supplied; otherwise derive a stable event id."""
    if supplied_event_id := _clean(payload.event_id):
        return supplied_event_id
    stable_fields = {
        "event_type": payload.event_type,
        "contact_id": lead.contact_id,
        "normalized_lead": lead.model_dump(mode="json"),
    }
    return f"derived_{stable_payload_hash(stable_fields)[:32]}"
