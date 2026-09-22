from __future__ import annotations

import pytest

from aisearcharab_api.staging_probe import (
    _check_security_headers,
    _decode_json_evidence,
    _percentile,
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
    ):
        with pytest.raises(ValueError):
            _validate_base_url(invalid)


def test_safe_origin_never_echoes_invalid_secret_bearing_urls() -> None:
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com/") == (
        "https://aisearcharab-api-staging-v2.onrender.com"
    )
    assert _safe_origin("https://user:secret@aisearcharab-api-staging-v2.onrender.com") is None
    assert _safe_origin("https://aisearcharab-api-staging-v2.onrender.com/?token=secret") is None


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


def test_security_header_gate_reports_missing_hsts_and_bad_request_id() -> None:
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
