from __future__ import annotations

import json
import logging
import re
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
ADMIN_CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
REQUEST_LOGGER = logging.getLogger("aisearcharab.request")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template.startswith("/"):
        return template
    # Never emit an arbitrary unmatched URL path. It can contain user-controlled
    # identifiers or deliberately injected sensitive material.
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
    # Deliberately omit query strings, raw URL paths, request/response bodies,
    # cookies, authorization headers and client/network identifiers.
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
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = -1
                if declared_size < 0:
                    response: Response = JSONResponse({"detail": "invalid content length"}, status_code=400)
                elif declared_size > request.app.state.settings.max_request_body_bytes:
                    response = JSONResponse({"detail": "request body too large"}, status_code=413)
                else:
                    response = await call_next(request)
            else:
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
