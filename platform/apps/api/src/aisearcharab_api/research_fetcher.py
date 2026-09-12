from __future__ import annotations

import hashlib
import http.client
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote, urlsplit

from .orchestration import StepTrace
from .orchestration_observability import TraceSink, WorkflowTraceContext
from .research_policy import ResearchSourceRegistry, ResearchTargetDenied, ResearchTargetPreflight, validate_connected_peer

_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/xhtml+xml",
        "application/xml",
        "text/html",
        "text/plain",
        "text/xml",
    }
)
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_HEADER_BYTES = 64 * 1024
_USER_AGENT = "AISearchResearchFetcher/1.0"


class ResearchFetchError(RuntimeError):
    """Base error for fail-closed external research fetching."""


class ResearchConnectionError(ResearchFetchError):
    pass


class ResearchProtocolError(ResearchFetchError):
    pass


class ResearchResponseTooLarge(ResearchFetchError):
    pass


class ResearchUnsupportedContent(ResearchFetchError):
    pass


class ResearchHTTPStatusError(ResearchFetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"research source returned HTTP {status_code}")
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ResearchFetchResult:
    source_id: str
    final_url: str
    status_code: int
    content_type: str
    charset: str | None
    body: bytes
    body_sha256: str
    byte_count: int
    redirect_count: int
    peer_ip: str


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection that never resolves the hostname after policy preflight."""

    def __init__(self, hostname: str, port: int, *, pinned_ip: str, timeout: float) -> None:
        super().__init__(hostname, port=port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS connection pinned to a reviewed IP while validating the original DNS hostname."""

    def __init__(
        self,
        hostname: str,
        port: int,
        *,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(hostname, port=port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except BaseException:
            raw_socket.close()
            raise


ConnectionFactory = Callable[[ResearchTargetPreflight, str], http.client.HTTPConnection]


def _default_connection_factory(preflight: ResearchTargetPreflight, pinned_ip: str) -> http.client.HTTPConnection:
    parsed = urlsplit(preflight.resolved.url)
    if parsed.scheme == "https":
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return _PinnedHTTPSConnection(
            preflight.resolved.host,
            preflight.resolved.port,
            pinned_ip=pinned_ip,
            timeout=preflight.timeout_seconds,
            context=context,
        )
    if parsed.scheme == "http":
        return _PinnedHTTPConnection(
            preflight.resolved.host,
            preflight.resolved.port,
            pinned_ip=pinned_ip,
            timeout=preflight.timeout_seconds,
        )
    raise ResearchProtocolError("unsupported preflight scheme")


def _request_target(url: str) -> str:
    parsed = urlsplit(url)
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        query = quote(parsed.query, safe="=&;%:@!$'()*+,/?-._~")
        return f"{path}?{query}"
    return path


def _validate_response_framing(response: http.client.HTTPResponse) -> None:
    header_bytes = sum(len(name) + len(value) + 4 for name, value in response.getheaders())
    if header_bytes > _MAX_HEADER_BYTES:
        raise ResearchProtocolError("research response headers exceed limit")

    content_lengths = response.headers.get_all("Content-Length") or []
    transfer_encodings = response.headers.get_all("Transfer-Encoding") or []
    if len(content_lengths) > 1:
        raise ResearchProtocolError("duplicate Content-Length is forbidden")
    if content_lengths and transfer_encodings:
        raise ResearchProtocolError("ambiguous response framing is forbidden")
    if transfer_encodings:
        normalized = ",".join(transfer_encodings).strip().lower()
        if normalized != "chunked":
            raise ResearchProtocolError("unsupported Transfer-Encoding")

    content_encoding = response.headers.get("Content-Encoding")
    if content_encoding and content_encoding.strip().lower() not in {"identity"}:
        raise ResearchUnsupportedContent("compressed research responses are not enabled")


def _content_metadata(response: http.client.HTTPResponse) -> tuple[str, str | None]:
    if response.headers.get("Content-Type") is None:
        raise ResearchUnsupportedContent("research response is missing Content-Type")
    content_type = response.headers.get_content_type().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ResearchUnsupportedContent(f"unsupported research content type: {content_type}")
    charset = response.headers.get_content_charset()
    return content_type, charset.lower() if charset else None


def _read_bounded_body(response: http.client.HTTPResponse, maximum: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise ResearchProtocolError("invalid Content-Length") from exc
        if declared < 0:
            raise ResearchProtocolError("negative Content-Length")
        if declared > maximum:
            raise ResearchResponseTooLarge("research response exceeds configured size limit")

    body = response.read(maximum + 1)
    if len(body) > maximum:
        raise ResearchResponseTooLarge("research response exceeds configured size limit")
    return body


class ResearchFetcher:
    """Pinned-IP GET fetcher behind a server-owned research-source registry.

    It has no public endpoint and performs no credential forwarding. Redirects are
    manual so every hop returns through `ResearchSourceRegistry.redirect`.
    """

    def __init__(
        self,
        registry: ResearchSourceRegistry,
        *,
        connection_factory: ConnectionFactory = _default_connection_factory,
        trace_sink: TraceSink | None = None,
    ) -> None:
        self._registry = registry
        self._connection_factory = connection_factory
        self._trace_sink = trace_sink

    def fetch(self, source_id: str, url: str, *, request_id: str | None = None) -> ResearchFetchResult:
        started = time.perf_counter()
        try:
            preflight = self._registry.preflight(source_id, url)
            while True:
                response, peer_ip = self._request_once(preflight)
                try:
                    if response.status in _REDIRECT_STATUSES:
                        location = response.headers.get("Location")
                        if not location:
                            raise ResearchProtocolError("redirect response is missing Location")
                        preflight = self._registry.redirect(preflight, location)
                        continue

                    if response.status < 200 or response.status >= 300:
                        raise ResearchHTTPStatusError(response.status)

                    _validate_response_framing(response)
                    content_type, charset = _content_metadata(response)
                    body = _read_bounded_body(response, preflight.max_response_bytes)
                    return ResearchFetchResult(
                        source_id=preflight.source_id,
                        final_url=preflight.resolved.url,
                        status_code=response.status,
                        content_type=content_type,
                        charset=charset,
                        body=body,
                        body_sha256=hashlib.sha256(body).hexdigest(),
                        byte_count=len(body),
                        redirect_count=preflight.redirect_count,
                        peer_ip=peer_ip,
                    )
                finally:
                    response.close()
        finally:
            if self._trace_sink is not None:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                self._trace_sink.emit(
                    context=WorkflowTraceContext(workflow="research_fetch", request_id=request_id),
                    trace=StepTrace(name=f"source:{source_id}", duration_ms=duration_ms),
                )

    def _request_once(self, preflight: ResearchTargetPreflight) -> tuple[http.client.HTTPResponse, str]:
        last_error: BaseException | None = None
        for pinned_ip in preflight.resolved.addresses:
            connection = self._connection_factory(preflight, pinned_ip)
            try:
                connection.connect()
                if connection.sock is None:
                    raise ResearchConnectionError("research connection did not expose a socket")
                peer = connection.sock.getpeername()[0]
                peer_ip = validate_connected_peer(preflight, str(peer))

                connection.putrequest("GET", _request_target(preflight.resolved.url), skip_host=True, skip_accept_encoding=True)
                connection.putheader("Host", preflight.resolved.host)
                connection.putheader("User-Agent", _USER_AGENT)
                connection.putheader(
                    "Accept",
                    "text/html,application/json,text/plain,application/xhtml+xml,application/xml,text/xml;q=0.9",
                )
                connection.putheader("Accept-Encoding", "identity")
                connection.putheader("Connection", "close")
                connection.endheaders()
                response = connection.getresponse()
                return response, peer_ip
            except (OSError, ssl.SSLError, http.client.HTTPException, ResearchTargetDenied) as exc:
                last_error = exc
                connection.close()
                continue

        raise ResearchConnectionError("all validated research addresses failed") from last_error
