from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
ADMIN_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "worker-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "manifest-src 'self'"
)
API_CSP = "default-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
REQUEST_LOGGER = logging.getLogger("aisearcharab.request")


class RequestBodyLimitMiddleware:
    """Fail closed on oversized request bodies, including chunked requests.

    The API does not expose streaming upload endpoints, so bounded buffering is an
    intentional trade-off: it prevents Content-Length bypasses while retaining a
    hard upper bound configured by MAX_REQUEST_BODY_BYTES.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared_length: int | None = None
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() != b"content-length":
                continue
            try:
                declared_length = int(raw_value.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                response = JSONResponse({"detail": "invalid content length"}, status_code=400)
                await response(scope, receive, send)
                return
            break

        if declared_length is not None:
            if declared_length < 0:
                response = JSONResponse({"detail": "invalid content length"}, status_code=400)
                await response(scope, receive, send)
                return
            if declared_length > self.max_bytes:
                response = JSONResponse({"detail": "request body too large"}, status_code=413)
                await response(scope, receive, send)
                return

        buffered: list[Message] = []
        total = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                response = JSONResponse({"detail": "request body too large"}, status_code=413)
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        index = 0

        async def replay_receive() -> Message:
            nonlocal index
            if index < len(buffered):
                message = buffered[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template.startswith("/"):
        return template
    return "__unmatched__"


def _log_request(
    *,
    request_id: str,
    environment: str,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    REQUEST_LOGGER.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "environment": environment,
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 3),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            response.headers["Cross-Origin-Resource-Policy"] = "same-site"
            response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
            response.headers["X-DNS-Prefetch-Control"] = "off"
            response.headers["Origin-Agent-Cluster"] = "?1"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = ADMIN_CSP if request.url.path.startswith("/admin") else API_CSP
            if request.app.state.settings.secure_cookies:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response
        finally:
            _log_request(
                request_id=request_id,
                environment=request.app.state.settings.environment,
                method=request.method,
                route=_route_template(request),
                status_code=status_code,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
