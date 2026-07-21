"""Webhook authentication helpers."""

from secrets import compare_digest

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


def verify_webhook_secret(request: Request) -> None:
    """Validate the configured shared secret without exposing it in logs or errors."""
    _verify_shared_secret(
        request,
        expected_secret=get_settings().webhook_shared_secret,
        header_name=get_settings().webhook_secret_header,
        service_name="Webhook",
    )


def verify_admin_secret(request: Request) -> None:
    """Validate the secret protecting administrative event recovery operations."""
    _verify_shared_secret(
        request,
        expected_secret=get_settings().admin_shared_secret,
        header_name=get_settings().admin_secret_header,
        service_name="Admin",
    )


def _verify_shared_secret(
    request: Request, expected_secret: str | None, header_name: str, service_name: str
) -> None:
    """Verify one configured header secret using a constant-time comparison."""
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} authentication is not configured.",
        )

    supplied_secret = request.headers.get(header_name)
    if supplied_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{service_name} credentials are required.",
        )
    if not compare_digest(supplied_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{service_name} credentials are invalid.",
        )
