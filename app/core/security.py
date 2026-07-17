"""Webhook authentication helpers."""

from secrets import compare_digest

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


def verify_webhook_secret(request: Request) -> None:
    """Validate the configured shared secret without exposing it in logs or errors."""
    settings = get_settings()
    expected_secret = settings.webhook_shared_secret
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook authentication is not configured.",
        )

    supplied_secret = request.headers.get(settings.webhook_secret_header)
    if supplied_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook credentials are required.",
        )
    if not compare_digest(supplied_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook credentials are invalid.",
        )
