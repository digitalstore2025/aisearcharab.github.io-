from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .staging_probe import (
    _decode_json,
    _percentile,
    _request,
    _safe_origin,
    _validate_base_url,
    run_probe,
)

ALLOWED_STAGING_ORIGIN = "https://aisearcharab-api-staging-v2.onrender.com"
EXPECTED_DATABASE_BINDING = "aisearcharab-staging-db-v2"
SEARCH_QUERY = "الذكاء الاصطناعي"
LOAD_EVIDENCE_MARKER = "bounded-load-v1"
TOTAL_REQUESTS = 40
CONCURRENCY = 4
REQUEST_TIMEOUT_SECONDS = 8.0
P95_BUDGET_MS = 2500.0
P99_BUDGET_MS = 5000.0
MAX_BUDGET_MS = 8000.0
MAX_ERROR_RATE = 0.0


@dataclass(frozen=True)
class Sample:
    status: int | None
    duration_ms: float | None
    app_took_ms: float | None
    error: str | None


def _validated_fixed_origin(raw: str) -> Any:
    parsed = _validate_base_url(raw)
    canonical = f"https://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
    if canonical != ALLOWED_STAGING_ORIGIN:
        raise ValueError("load probe target is not the approved AISearcharab staging origin")
    return parsed


def _search_path() -> str:
    return "/v1/search?" + urlencode(
        {"q": SEARCH_QUERY, "limit": 5, "_evidence": LOAD_EVIDENCE_MARKER}
    )


def _one_search(parsed: Any, addresses: list[str]) -> Sample:
    started = time.perf_counter()
    try:
        status, _headers, body, duration_ms = _request(
            parsed,
            _search_path(),
            addresses=addresses,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if status != 200:
            return Sample(status=status, duration_ms=duration_ms, app_took_ms=None, error=f"http_status:{status}")
        payload = _decode_json(body, "search")
        if payload.get("query") != SEARCH_QUERY:
            return Sample(status=status, duration_ms=duration_ms, app_took_ms=None, error="search_query_mismatch")
        results = payload.get("results")
        if not isinstance(results, list):
            return Sample(status=status, duration_ms=duration_ms, app_took_ms=None, error="search_results_not_list")
        app_took = payload.get("took_ms")
        if not isinstance(app_took, (int, float)) or app_took < 0:
            return Sample(status=status, duration_ms=duration_ms, app_took_ms=None, error="search_took_ms_invalid")
        return Sample(status=status, duration_ms=duration_ms, app_took_ms=float(app_took), error=None)
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        return Sample(
            status=None,
            duration_ms=duration_ms,
            app_took_ms=None,
            error=f"{type(exc).__name__}",
        )


def _latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
    return {
        "p50_ms": round(_percentile(values, 0.50), 3),
        "p95_ms": round(_percentile(values, 0.95), 3),
        "p99_ms": round(_percentile(values, 0.99), 3),
        "max_ms": round(max(values), 3),
    }


def _summarize(samples: list[Sample], elapsed_seconds: float) -> dict[str, Any]:
    total = len(samples)
    failed = sum(1 for sample in samples if sample.error is not None)
    durations = [sample.duration_ms for sample in samples if sample.duration_ms is not None]
    app_durations = [sample.app_took_ms for sample in samples if sample.app_took_ms is not None]
    status_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for sample in samples:
        status_key = str(sample.status) if sample.status is not None else "transport_error"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        if sample.error is not None:
            error_counts[sample.error] = error_counts.get(sample.error, 0) + 1
    return {
        "requests": total,
        "concurrency": CONCURRENCY,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rps": round(total / elapsed_seconds, 3) if elapsed_seconds > 0 else 0.0,
        "failed_requests": failed,
        "error_rate": round(failed / total, 6) if total else 1.0,
        "status_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(sorted(error_counts.items())),
        "network_latency": _latency_summary([float(value) for value in durations]),
        "application_latency": _latency_summary([float(value) for value in app_durations]),
    }


def _slo_failures(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if summary["requests"] != TOTAL_REQUESTS:
        failures.append(f"workload count mismatch: expected {TOTAL_REQUESTS}, got {summary['requests']}")
    if summary["error_rate"] > MAX_ERROR_RATE:
        failures.append(f"error rate exceeded budget: {summary['error_rate']} > {MAX_ERROR_RATE}")
    latency = summary["network_latency"]
    if latency["p95_ms"] > P95_BUDGET_MS:
        failures.append(f"p95 exceeded budget: {latency['p95_ms']}ms > {P95_BUDGET_MS}ms")
    if latency["p99_ms"] > P99_BUDGET_MS:
        failures.append(f"p99 exceeded budget: {latency['p99_ms']}ms > {P99_BUDGET_MS}ms")
    if latency["max_ms"] > MAX_BUDGET_MS:
        failures.append(f"max latency exceeded budget: {latency['max_ms']}ms > {MAX_BUDGET_MS}ms")
    return failures


def run_load_probe(base_url: str, *, expected_revision: str) -> dict[str, Any]:
    parsed = _validated_fixed_origin(base_url)
    preflight = run_probe(
        base_url,
        samples=3,
        timeout=REQUEST_TIMEOUT_SECONDS,
        expected_revision=expected_revision,
        expected_database_binding=EXPECTED_DATABASE_BINDING,
    )
    if not preflight.get("overall_pass"):
        return {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "target": {"origin": ALLOWED_STAGING_ORIGIN},
            "workload": {"state": "skipped", "reason": "staging_preflight_failed"},
            "preflight": preflight,
            "slo": _slo_contract(),
            "failures": ["staging preflight failed; load workload was not started"],
            "overall_pass": False,
        }

    addresses = preflight.get("target", {}).get("resolved_public_addresses")
    if not isinstance(addresses, list) or not addresses or not all(isinstance(item, str) for item in addresses):
        raise RuntimeError("preflight did not provide validated public addresses")

    started = time.perf_counter()
    samples: list[Sample] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="aisearcharab-load") as executor:
        futures = [executor.submit(_one_search, parsed, addresses) for _ in range(TOTAL_REQUESTS)]
        for future in as_completed(futures):
            samples.append(future.result())
    elapsed = time.perf_counter() - started

    summary = _summarize(samples, elapsed)
    failures = _slo_failures(summary)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "target": {
            "origin": ALLOWED_STAGING_ORIGIN,
            "revision": expected_revision.lower(),
            "database_binding": EXPECTED_DATABASE_BINDING,
        },
        "preflight": preflight,
        "workload": {
            "state": "completed",
            "method": "GET",
            "endpoint": "/v1/search",
            "query_fixture": SEARCH_QUERY,
            "read_only": True,
            "query_logging_suppressed": True,
            "evidence_marker": LOAD_EVIDENCE_MARKER,
            "generated_answers": False,
            "summary": summary,
        },
        "slo": _slo_contract(),
        "failures": failures,
        "overall_pass": not failures,
    }


def _slo_contract() -> dict[str, Any]:
    return {
        "scope": "bounded_staging_smoke_load",
        "requests": TOTAL_REQUESTS,
        "concurrency": CONCURRENCY,
        "max_error_rate": MAX_ERROR_RATE,
        "network_p95_budget_ms": P95_BUDGET_MS,
        "network_p99_budget_ms": P99_BUDGET_MS,
        "network_max_budget_ms": MAX_BUDGET_MS,
        "production_capacity_claim": False,
    }


def _write_evidence(path: str | Path, evidence: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect bounded AISearcharab staging load/SLO evidence")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", default="/tmp/aisearcharab-staging-load-evidence.json")
    args = parser.parse_args()

    try:
        evidence = run_load_probe(args.base_url, expected_revision=args.expected_revision)
    except Exception as exc:
        evidence = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "target": {"origin": _safe_origin(args.base_url)},
            "workload": {"state": "not_started"},
            "slo": _slo_contract(),
            "failures": [f"load probe exception: {type(exc).__name__}: {exc}"],
            "overall_pass": False,
        }

    _write_evidence(args.output, evidence)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if evidence["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
