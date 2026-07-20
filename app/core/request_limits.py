"""ASGI middleware for protecting webhook endpoints from oversized bodies."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class RequestTooLargeError(Exception):
    """Raised when an HTTP request exceeds the configured body limit."""


class RequestSizeLimitMiddleware:
    """Reject requests exceeding the configured byte limit before application processing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap the ASGI receive channel and count inbound request bytes."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = get_settings().max_request_size_bytes
        content_length = _content_length(scope)
        if content_length is not None and content_length > max_bytes:
            await _too_large_response(max_bytes)(scope, receive, send)
            return

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_bytes:
                    raise RequestTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLargeError:
            await _too_large_response(max_bytes)(scope, receive, send)


def _content_length(scope: Scope) -> int | None:
    for key, value in scope["headers"]:
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _too_large_response(max_bytes: int) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": f"Request body exceeds the {max_bytes}-byte limit."},
    )
