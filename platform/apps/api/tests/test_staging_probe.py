from __future__ import annotations

import concurrent.futures

import pytest

from aisearcharab_api.staging_probe import (
    _check_security_headers,
    _decode_json_evidence,
    _percentile,
    _resolve_public_addresses,
    _safe_origin,
    _validate_base_url,
)


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
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com/") == (
        "https://aisearcharab-api-staging-v2.onrender.com"
    )
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
    headers = {
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
    assert _check_security_headers(headers) == []


def test_security_header_gate_reports_missing_hsts_bad_request_id_and_permissions_policy() -> None:
    headers = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
        "cross-origin-opener-policy": "same-origin",
        "cross-origin-resource-policy": "same-site",
        "x-permitted-cross-domain-policies": "none",
        "x-dns-prefetch-control": "off",
        "origin-agent-cluster": "?1",
        "x-robots-tag": "noindex, nofollow",
        "cache-control": "no-store",
        "x-request-id": "bad",
        "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    }
    failures = _check_security_headers(headers)
    assert any(item.startswith("strict-transport-security:") for item in failures)
    assert any(item.startswith("permissions-policy:") for item in failures)
    assert "x-request-id: missing or invalid" in failures


def test_security_header_gate_rejects_csp_none_combined_with_other_sources() -> None:
    headers = {
        **{
            key: value
            for key, value in {
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
            }.items()
        },
        "x-request-id": "staging-probe-request-1234",
        "content-security-policy": "default-src 'none' https:; frame-ancestors 'none' https:",
    }
    failures = _check_security_headers(headers)
    assert any(item.startswith("content-security-policy:") for item in failures)


def test_dns_resolution_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyFuture:
        def result(self, timeout: float):
            raise concurrent.futures.TimeoutError

        def cancel(self) -> bool:
            return True

    class DummyExecutor:
        def submit(self, fn):
            return DummyFuture()

        def shutdown(self, wait: bool, cancel_futures: bool) -> None:
            assert wait is False
            assert cancel_futures is True

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", lambda max_workers: DummyExecutor())
    with pytest.raises(RuntimeError, match="DNS resolution timed out"):
        _resolve_public_addresses("example.com", 443, timeout=0.01)
