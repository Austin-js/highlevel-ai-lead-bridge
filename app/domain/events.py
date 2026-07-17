"""Incoming HighLevel-compatible event schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContactPayload(BaseModel):
    """Contact fields accepted from a HighLevel workflow event."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class HighLevelEventPayload(BaseModel):
    """The supported subset of a HighLevel workflow webhook payload."""

    model_config = ConfigDict(extra="allow")

    event_id: str | None = None
    event_type: str = "contact.created"
    location_id: str | None = None
    contact: ContactPayload


class WebhookReceipt(BaseModel):
    """Public acknowledgement returned after webhook intake."""

    status: str
    event_id: str
    duplicate: bool
    fallback_used: bool | None = None
