"""Structured lead-summary schema."""

from typing import Literal

from pydantic import BaseModel, Field

Urgency = Literal["low", "medium", "high"]
Qualification = Literal["unqualified", "uncertain", "qualified", "high_intent"]


class LeadSummary(BaseModel):
    """A concise, validated lead summary for operations staff."""

    overview: str = Field(min_length=1, max_length=1000)
    intent: str = Field(min_length=1, max_length=500)
    urgency: Urgency
    qualification: Qualification
    key_details: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1, max_length=500)
    recommended_response_time_minutes: int | None = Field(default=None, ge=1, le=10080)
    confidence: float = Field(ge=0, le=1)
