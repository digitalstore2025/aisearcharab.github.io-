from __future__ import annotations

import pytest

import aisearcharab_api.staging_probe as staging_probe

from aisearcharab_api.staging_probe import (
    _check_security_headers,
    _decode_json_evidence,
    _percentile,
    _resolve_public_addresses,
    _safe_origin,
    _validate_base_url,
)


def _hardened_headers() -> dict[str, str]:
    return {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "cross-origin-opener-policy": "same-origin",
        "cross-origin-resource-policy": "same-site",
        "x-permitted-cross-domain-policies": "none",
        "x-dns-prefetch-control": "off",
        "origin-agent-cluster": "?1",
        "x-robots-tag": "noindex, nofollow",
        "cache-control": "no-store",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-request-id": "staging-probe-request-1234",
        "content-security-policy": (
            "default-src 'none'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        ),
    }


def test_staging_origin_requires_https_without_credentials_or_nested_path() -> None:
    parsed = _validate_base_url("https://aisearcharab-api-staging-v2.onrender.com/")
    assert parsed.hostname == "aisearcharab-api-staging-v2.onrender.com"
    for invalid in (
        "http://aisearcharab-api-staging-v2.onrender.com",
        "https://user:secret@aisearcharab-api-staging-v2.onrender.com",
        "https://aisearcharab-api-staging-v2.onrender.com/health/live",
        "https://aisearcharab-api-staging-v2.onrender.com/?token=secret",
        "https://aisearcharab-api-staging-v2.onrender.com:99999",
        "https://aisearcharab-api-staging-v2.onrender.com:notaport",
    ):
        with pytest.raises(ValueError):
            _validate_base_url(invalid)


def test_safe_origin_never_echoes_invalid_secret_bearing_urls_or_ports() -> None:
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com/") == "https://aisearcharab-api-staging-v2.onrender.com"
    assert _safe_origin("https://user:secret@aisearcharab-api-staging-v2.onrender.com") is None
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com/?token=secret") is None
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com:99999") is None
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com:notaport") is None


def test_malformed_json_is_recorded_without_discarding_evidence() -> None:
    failures: list[str] = []
    value = _decode_json_evidence(b"not-json", "liveness", failures)
    assert value == {}
    assert failures == ["liveness did not return valid UTF-8 JSON"]


def test_percentile_interpolates_deterministically() -> None:
    values = [10.0, 20.0, 30.0, 40.0]
    assert _percentile(values, 0.50) == 25.0
    assert _percentile(values, 0.95) == pytest.approx(38.5)
    assert _percentile([7.0], 0.99) == 7.0


def test_security_header_gate_accepts_hardened_api_headers() -> None:
    assert _check_security_headers(_hardened_headers()) == []


def test_security_header_gate_reports_missing_controls() -> None:
    headers = _hardened_headers()
    headers.pop("strict-transport-security")
    headers.pop("permissions-policy")
    headers["x-request-id"] = "bad"
    failures = _check_security_headers(headers)
    assert any(item.startswith("strict-transport-security:") for item in failures)
    assert any(item.startswith("permissions-policy:") for item in failures)
    assert "x-request-id: missing or invalid" in failures


def test_security_header_gate_rejects_csp_none_combined_with_other_sources() -> None:
    headers = _hardened_headers()
    headers["content-security-policy"] = "default-src 'none' https:; frame-ancestors 'none' https:"
    failures = _check_security_headers(headers)
    assert any(item.startswith("content-security-policy:") for item in failures)


def test_security_header_gate_rejects_duplicate_csp_directives() -> None:
    headers = _hardened_headers()
    headers["content-security-policy"] = "default-src 'none'; default-src https:; frame-ancestors 'none'"
    failures = _check_security_headers(headers)
    assert "content-security-policy: duplicate directives are not accepted" in failures


def test_security_header_gate_requires_request_id_correlation() -> None:
    headers = _hardened_headers()
    headers["x-request-id"] = "different-request-id-1234"
    failures = _check_security_headers(headers, expected_request_id="staging-probe-request-1234")
    assert "x-request-id: response did not preserve the supplied correlation ID" in failures


def test_dns_resolution_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyQueue:
        def close(self) -> None:
            pass
        def empty(self) -> bool:
            return True

    class DummyProcess:
        def __init__(self) -> None:
            self.terminated = False
        def start(self) -> None:
            pass
        def join(self, timeout: float) -> None:
            pass
        def is_alive(self) -> bool:
            return not self.terminated
        def terminate(self) -> None:
            self.terminated = True

    class DummyContext:
        def Queue(self, maxsize: int):
            assert maxsize == 1
            return DummyQueue()
        def Process(self, *, target, args, daemon: bool):
            assert daemon is True
            return DummyProcess()

    monkeypatch.setattr("aisearcharab_api.staging_probe.multiprocessing.get_context", lambda mode: DummyContext())
    with pytest.raises(RuntimeError, match="DNS resolution timed out"):
        _resolve_public_addresses("example.com", 443, timeout=0.01)


def test_http_read_enforces_wall_clock_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummySocket:
        def settimeout(self, value: float) -> None:
            pass
        def close(self) -> None:
            pass

    class DummyResponse:
        status = 200
        def getheaders(self):
            return []
        def read(self, size: int) -> bytes:
            return b"x"

    class DummyConnection:
        def __init__(self, *args, **kwargs) -> None:
            self.sock = None
        def request(self, *args, **kwargs) -> None:
            pass
        def getresponse(self):
            return DummyResponse()
        def close(self) -> None:
            pass

    clock = iter([0.0, 0.0, 0.1, 0.2, 1.1])
    monkeypatch.setattr(staging_probe.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(staging_probe.time, "perf_counter", lambda: 0.0)
    monkeypatch.setattr(staging_probe.socket, "create_connection", lambda *args, **kwargs: DummySocket())
    monkeypatch.setattr(staging_probe.ssl, "create_default_context", lambda: type("C", (), {"wrap_socket": lambda self, sock, server_hostname: DummySocket()})())
    monkeypatch.setattr(staging_probe.http.client, "HTTPSConnection", DummyConnection)

    parsed = staging_probe._validate_base_url("https://aisearcharab-api-staging-v2.onrender.com")
    with pytest.raises(RuntimeError, match="all validated staging addresses failed"):
        staging_probe._request(parsed, "/health/live", addresses=["8.8.8.8"], timeout=1.0)
