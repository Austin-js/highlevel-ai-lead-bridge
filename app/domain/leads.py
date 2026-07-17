"""Normalized lead representation."""

from typing import Any

from pydantic import BaseModel, Field


class Lead(BaseModel):
    """A clean, provider-neutral representation of a lead."""

    contact_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    service_requested: str | None = None
    preferred_schedule: str | None = None
    message: str | None = None
    appointment_status: str | None = None
    pipeline_id: str | None = None
    opportunity_id: str | None = None
    location_id: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
