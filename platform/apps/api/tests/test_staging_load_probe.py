from __future__ import annotations

import pytest

import aisearcharab_api.staging_load_probe as load_probe
from aisearcharab_api.staging_load_probe import Sample


def _passing_preflight() -> dict:
    return {
        "overall_pass": True,
        "target": {
            "origin": load_probe.ALLOWED_STAGING_ORIGIN,
            "resolved_public_addresses": ["8.8.8.8"],
        },
        "checks": {
            "deployment": {
                "revision": "a" * 40,
                "database_binding": load_probe.EXPECTED_DATABASE_BINDING,
            }
        },
        "failures": [],
    }


def test_load_probe_rejects_any_non_approved_origin() -> None:
    with pytest.raises(ValueError, match="approved AISearcharab staging origin"):
        load_probe.run_load_probe(
            "https://example.com",
            expected_revision="a" * 40,
        )


def test_load_probe_skips_workload_when_preflight_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        load_probe,
        "run_probe",
        lambda *args, **kwargs: {
            "overall_pass": False,
            "target": {"origin": load_probe.ALLOWED_STAGING_ORIGIN},
            "failures": ["revision mismatch"],
        },
    )

    evidence = load_probe.run_load_probe(
        load_probe.ALLOWED_STAGING_ORIGIN,
        expected_revision="a" * 40,
    )

    assert evidence["overall_pass"] is False
    assert evidence["workload"]["state"] == "skipped"
    assert evidence["slo"]["production_capacity_claim"] is False


def test_load_probe_passes_bounded_workload_with_zero_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(load_probe, "run_probe", lambda *args, **kwargs: _passing_preflight())
    monkeypatch.setattr(
        load_probe,
        "_one_search",
        lambda parsed, addresses: Sample(
            status=200,
            duration_ms=120.0,
            app_took_ms=25.0,
            error=None,
        ),
    )

    evidence = load_probe.run_load_probe(
        load_probe.ALLOWED_STAGING_ORIGIN,
        expected_revision="a" * 40,
    )

    assert evidence["overall_pass"] is True
    summary = evidence["workload"]["summary"]
    assert summary["requests"] == load_probe.TOTAL_REQUESTS
    assert summary["failed_requests"] == 0
    assert summary["error_rate"] == 0.0
    assert summary["network_latency"]["p95_ms"] == 120.0
    assert evidence["slo"]["production_capacity_claim"] is False


def test_slo_gate_fails_on_error_rate() -> None:
    samples = [
        Sample(status=200, duration_ms=100.0, app_took_ms=10.0, error=None)
        for _ in range(load_probe.TOTAL_REQUESTS - 1)
    ] + [Sample(status=503, duration_ms=100.0, app_took_ms=None, error="http_status:503")]
    summary = load_probe._summarize(samples, 2.0)
    failures = load_probe._slo_failures(summary)
    assert any("error rate exceeded budget" in item for item in failures)


def test_slo_gate_fails_on_tail_latency() -> None:
    samples = [
        Sample(status=200, duration_ms=100.0, app_took_ms=10.0, error=None)
        for _ in range(load_probe.TOTAL_REQUESTS - 2)
    ] + [
        Sample(status=200, duration_ms=7000.0, app_took_ms=10.0, error=None),
        Sample(status=200, duration_ms=9000.0, app_took_ms=10.0, error=None),
    ]
    summary = load_probe._summarize(samples, 10.0)
    failures = load_probe._slo_failures(summary)
    assert any("p99 exceeded budget" in item for item in failures)
    assert any("max latency exceeded budget" in item for item in failures)


def test_summary_never_treats_transport_errors_as_http_success() -> None:
    samples = [
        Sample(status=None, duration_ms=None, app_took_ms=None, error="TimeoutError"),
        Sample(status=200, duration_ms=120.0, app_took_ms=20.0, error=None),
    ]
    summary = load_probe._summarize(samples, 1.0)
    assert summary["failed_requests"] == 1
    assert summary["status_counts"]["transport_error"] == 1
    assert summary["error_counts"]["TimeoutError"] == 1


def test_slo_contract_is_intentionally_bounded() -> None:
    contract = load_probe._slo_contract()
    assert contract["requests"] == 40
    assert contract["concurrency"] == 4
    assert contract["production_capacity_claim"] is False
