from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import MappingProxyType

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SECURITY_HEADERS = MappingProxyType(
    {
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Referrer-Policy": "no-referrer",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
)


def apply_security_headers(response: Response) -> Response:
    """Apply conservative headers to an API response."""

    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Reusable ASGI middleware; application wiring is intentionally explicit."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        return apply_security_headers(await call_next(request))
