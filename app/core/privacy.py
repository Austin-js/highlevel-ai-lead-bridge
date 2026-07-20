"""Helpers for privacy-safe log metadata."""

import hashlib

from app.domain.leads import Lead


def contact_log_context(lead: Lead, event_id: str) -> dict[str, str]:
    """Return correlation fields without including raw email or phone information."""
    context = {"event_id": event_id, "contact_id": lead.contact_id or "unknown"}
    if lead.email:
        context["email_hash"] = hashlib.sha256(lead.email.lower().encode("utf-8")).hexdigest()[:16]
    if lead.phone:
        context["phone_last4"] = lead.phone[-4:]
    return context
