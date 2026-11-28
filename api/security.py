"""Request-boundary hardening (TASK-019/021): body cap, response headers, optional passcode.

Pure ASGI middleware (not `BaseHTTPMiddleware`) so Server-Sent Events are never buffered.
"""

from __future__ import annotations

import hmac
import json
from typing import Annotated

from fastapi import Header
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import config
from api.errors import ApiError, error_body

MAX_BODY_BYTES = 64 * 1024  # every legitimate request here is a few hundred bytes

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)


class SecurityMiddleware:
    """Reject oversized bodies early and add conservative headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            body = json.dumps(error_body("ValidationError", "The request is too large.")).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        *SECURITY_HEADERS,
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                extra = [(n, v) for n, v in SECURITY_HEADERS if n not in present]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def require_passcode(
    x_demo_passcode: Annotated[str | None, Header(max_length=200)] = None,
) -> None:
    """FastAPI dependency: when `DEMO_PASSCODE` is set, the header must match (constant time)."""
    expected = config.demo_passcode()
    if expected is None:
        return
    supplied = x_demo_passcode or ""
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ApiError(401, "Unauthorized", "A valid passcode is required.")


__all__ = ["MAX_BODY_BYTES", "SecurityMiddleware", "require_passcode"]
