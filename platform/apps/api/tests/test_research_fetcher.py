from __future__ import annotations

import hashlib
import socket
from email.message import Message

import pytest

from aisearcharab_api.orchestration import StepTrace
from aisearcharab_api.orchestration_observability import WorkflowTraceContext
from aisearcharab_api.research_fetcher import (
    ResearchConnectionError,
    ResearchFetcher,
    ResearchProtocolError,
    ResearchResponseTooLarge,
    ResearchUnsupportedContent,
    _PinnedHTTPSConnection,
)
from aisearcharab_api.research_policy import ResearchSourcePolicy, ResearchSourceRegistry, ResearchTargetDenied


class FakePeerSocket:
    def __init__(self, peer_ip: str) -> None:
        self.peer_ip = peer_ip
        self.closed = False

    def getpeername(self):
        return (self.peer_ip, 443)

    def close(self) -> None:
        self.closed = True


class FakeResponse:
    def __init__(self, *, status: int = 200, headers: list[tuple[str, str]] | None = None, body: bytes = b"ok") -> None:
        self.status = status
        self.headers = Message()
        effective_headers = [("Content-Type", "text/plain; charset=utf-8")] if headers is None else headers
        for name, value in effective_headers:
            self.headers[name] = value
        self._body = body
        self.closed = False

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self.headers.items())

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, response: FakeResponse, *, peer_ip: str = "1.1.1.1") -> None:
        self.response = response
        self.sock = FakePeerSocket(peer_ip)
        self.closed = False
        self.request: tuple[str, str] | None = None
        self.headers: list[tuple[str, str]] = []

    def connect(self) -> None:
        return None

    def putrequest(self, method: str, target: str, **_kwargs) -> None:
        self.request = (method, target)

    def putheader(self, name: str, value: str) -> None:
        self.headers.append((name, value))

    def endheaders(self) -> None:
        return None

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class RecordingTraceSink:
    def __init__(self) -> None:
        self.events: list[tuple[WorkflowTraceContext, StepTrace]] = []

    def emit(self, *, context: WorkflowTraceContext, trace: StepTrace) -> None:
        self.events.append((context, trace))


def _source(**overrides: object) -> ResearchSourcePolicy:
    values: dict[str, object] = {
        "source_id": "official-docs",
        "allowed_hosts": frozenset({"docs.example.com"}),
    }
    values.update(overrides)
    return ResearchSourcePolicy(**values)  # type: ignore[arg-type]


def _public_dns(monkeypatch: pytest.MonkeyPatch, addresses: tuple[str, ...] = ("1.1.1.1",)) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)) for address in addresses
        ],
    )


def _fetcher(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[FakeResponse],
    *,
    peer_ips: list[str] | None = None,
    policy: ResearchSourcePolicy | None = None,
    trace_sink: RecordingTraceSink | None = None,
) -> tuple[ResearchFetcher, list[FakeConnection]]:
    _public_dns(monkeypatch)
    registry = ResearchSourceRegistry([policy or _source()])
    connections: list[FakeConnection] = []
    peers = list(peer_ips or ["1.1.1.1"] * len(responses))

    def factory(_preflight, _pinned_ip):
        index = len(connections)
        connection = FakeConnection(responses[index], peer_ip=peers[index])
        connections.append(connection)
        return connection

    return ResearchFetcher(registry, connection_factory=factory, trace_sink=trace_sink), connections


def test_fetches_allowlisted_source_with_pinned_peer_and_integrity_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "مرحبا".encode()
    response = FakeResponse(body=body)
    sink = RecordingTraceSink()
    fetcher, connections = _fetcher(monkeypatch, [response], trace_sink=sink)

    result = fetcher.fetch("official-docs", "https://docs.example.com/دليل?q=بحث", request_id="req-123")

    assert result.body == body
    assert result.body_sha256 == hashlib.sha256(body).hexdigest()
    assert result.peer_ip == "1.1.1.1"
    assert result.content_type == "text/plain"
    assert result.charset == "utf-8"
    assert result.byte_count == len(body)
    assert connections[0].request == ("GET", "/%D8%AF%D9%84%D9%8A%D9%84?q=%D8%A8%D8%AD%D8%AB")
    headers = dict(connections[0].headers)
    assert headers["Host"] == "docs.example.com"
    assert headers["Accept-Encoding"] == "identity"
    assert "Authorization" not in headers
    assert "Cookie" not in headers
    assert response.closed is True
    assert connections[0].closed is True
    assert sink.events[0][0] == WorkflowTraceContext(workflow="research_fetch", request_id="req-123")
    assert sink.events[0][1].name == "fetch"


def test_redirect_is_manual_revalidated_and_each_connection_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    first = FakeResponse(status=302, headers=[("Location", "/final"), ("Content-Type", "text/plain")])
    second = FakeResponse(body=b"final")
    fetcher, connections = _fetcher(monkeypatch, [first, second], policy=_source(max_redirects=2))

    result = fetcher.fetch("official-docs", "https://docs.example.com/start")

    assert result.final_url == "https://docs.example.com/final"
    assert result.redirect_count == 1
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)
    assert first.closed and second.closed


def test_redirect_cannot_escape_source_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(
        status=302,
        headers=[("Location", "https://attacker.example/private"), ("Content-Type", "text/plain")],
    )
    fetcher, connections = _fetcher(monkeypatch, [response])

    with pytest.raises(ResearchTargetDenied, match="not allowlisted"):
        fetcher.fetch("official-docs", "https://docs.example.com/start")
    assert connections[0].closed is True


def test_connected_peer_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher, connections = _fetcher(monkeypatch, [FakeResponse()], peer_ips=["8.8.8.8"])

    with pytest.raises(ResearchConnectionError):
        fetcher.fetch("official-docs", "https://docs.example.com/")
    assert connections[0].closed is True


def test_oversized_declared_body_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _source(max_response_bytes=4)
    response = FakeResponse(headers=[("Content-Type", "text/plain"), ("Content-Length", "5")], body=b"12345")
    fetcher, _connections = _fetcher(monkeypatch, [response], policy=policy)

    with pytest.raises(ResearchResponseTooLarge):
        fetcher.fetch("official-docs", "https://docs.example.com/")


def test_streamed_body_over_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _source(max_response_bytes=4)
    response = FakeResponse(headers=[("Content-Type", "text/plain")], body=b"12345")
    fetcher, _connections = _fetcher(monkeypatch, [response], policy=policy)

    with pytest.raises(ResearchResponseTooLarge):
        fetcher.fetch("official-docs", "https://docs.example.com/")


def test_ambiguous_framing_and_compression_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    ambiguous = FakeResponse(
        headers=[
            ("Content-Type", "text/plain"),
            ("Content-Length", "2"),
            ("Transfer-Encoding", "chunked"),
        ]
    )
    fetcher, _connections = _fetcher(monkeypatch, [ambiguous])
    with pytest.raises(ResearchProtocolError, match="ambiguous"):
        fetcher.fetch("official-docs", "https://docs.example.com/")

    compressed = FakeResponse(headers=[("Content-Type", "text/plain"), ("Content-Encoding", "gzip")])
    fetcher, _connections = _fetcher(monkeypatch, [compressed])
    with pytest.raises(ResearchUnsupportedContent, match="compressed"):
        fetcher.fetch("official-docs", "https://docs.example.com/")


def test_binary_content_and_missing_content_type_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    binary = FakeResponse(headers=[("Content-Type", "application/octet-stream")])
    fetcher, _connections = _fetcher(monkeypatch, [binary])
    with pytest.raises(ResearchUnsupportedContent, match="content type"):
        fetcher.fetch("official-docs", "https://docs.example.com/")

    missing = FakeResponse(headers=[])
    fetcher, _connections = _fetcher(monkeypatch, [missing])
    with pytest.raises(ResearchUnsupportedContent, match="missing"):
        fetcher.fetch("official-docs", "https://docs.example.com/")


def test_fragment_and_excessive_url_are_rejected_before_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def should_not_resolve(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(socket, "getaddrinfo", should_not_resolve)
    registry = ResearchSourceRegistry([_source()])
    fetcher = ResearchFetcher(registry)
    with pytest.raises(ResearchProtocolError, match="fragments"):
        fetcher.fetch("official-docs", "https://docs.example.com/a#fragment")
    with pytest.raises(ResearchProtocolError, match="length"):
        fetcher.fetch("official-docs", "https://docs.example.com/" + "a" * 9000)
    assert calls == 0


def test_excessive_dns_fanout_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    addresses = tuple(f"1.1.1.{value}" for value in range(1, 10))
    _public_dns(monkeypatch, addresses)
    registry = ResearchSourceRegistry([_source()])
    fetcher = ResearchFetcher(registry, connection_factory=lambda *_args: pytest.fail("must not connect"))
    with pytest.raises(ResearchTargetDenied, match="too many addresses"):
        fetcher.fetch("official-docs", "https://docs.example.com/")


def test_pinned_https_connection_uses_ip_for_tcp_and_hostname_for_sni(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    raw = FakePeerSocket("1.1.1.1")

    def fake_create_connection(address, timeout, source_address):
        calls["address"] = address
        calls["timeout"] = timeout
        calls["source_address"] = source_address
        return raw

    class FakeContext:
        def wrap_socket(self, sock, *, server_hostname):
            calls["wrapped"] = sock
            calls["server_hostname"] = server_hostname
            return sock

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    connection = _PinnedHTTPSConnection(
        "docs.example.com",
        443,
        pinned_ip="1.1.1.1",
        timeout=7.0,
        context=FakeContext(),  # type: ignore[arg-type]
    )
    connection.connect()

    assert calls["address"] == ("1.1.1.1", 443)
    assert calls["server_hostname"] == "docs.example.com"
    assert connection.sock is raw
