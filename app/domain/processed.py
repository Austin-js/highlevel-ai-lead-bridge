"""A summarized lead event ready for downstream delivery."""

from dataclasses import dataclass

from app.domain.leads import Lead
from app.domain.summaries import LeadSummary


@dataclass(frozen=True)
class ProcessedLeadEvent:
    """The minimum safe data needed by notification integrations."""

    event_id: str
    lead: Lead
    summary: LeadSummary
    fallback_used: bool
