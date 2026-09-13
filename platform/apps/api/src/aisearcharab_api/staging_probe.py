from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
MAX_RESPONSE_BYTES = 128 * 1024
REQUIRED_SECURITY_HEADERS = {
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
    "strict-transport-security": "max-age=31536000; includeSubDomains",
}


def _validate_base_url(raw: str) -> SplitResult:
    parsed = urlsplit(raw.strip())
    if parsed.scheme != "https":
        raise ValueError("staging probe requires HTTPS")
    if not parsed.hostname:
        raise ValueError("staging URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("staging URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("staging URL must not contain query parameters or fragments")
    if parsed.path not in {"", "/"}:
        raise ValueError("staging URL must be an origin, not a nested path")
    return parsed


def _resolve_public_addresses(hostname: str, port: int) -> list[str]:
    addresses: set[str] = set()
    for family, socktype, proto, _canonname, sockaddr in socket.getaddrinfo(
        hostname, port, type=socket.SOCK_STREAM
    ):
        del family, socktype, proto
        raw_ip = sockaddr[0]
        ip = ipaddress.ip_address(raw_ip)
        if not ip.is_global:
            raise RuntimeError(f"staging hostname resolved to a non-public address: {raw_ip}")
        addresses.add(ip.compressed)
    if not addresses:
        raise RuntimeError("staging hostname did not resolve")
    return sorted(addresses)


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _request(
    parsed: SplitResult,
    path: str,
    *,
    timeout: float,
    host_header: str | None = None,
) -> tuple[int, dict[str, str], bytes, float]:
    host = parsed.hostname
    if host is None:
        raise RuntimeError("validated URL lost hostname")
    port = parsed.port or 443
    connection = http.client.HTTPSConnection(
        host,
        port,
        timeout=timeout,
        context=ssl.create_default_context(),
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "AISearcharab-Staging-Evidence/1.0",
    }
    if host_header is not None:
        headers["Host"] = host_header
    started = time.perf_counter()
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)
        duration_ms = (time.perf_counter() - started) * 1000
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError(f"response body exceeded {MAX_RESPONSE_BYTES} bytes")
        normalized_headers = {key.lower(): value for key, value in response.getheaders()}
        return response.status, normalized_headers, body, duration_ms
    finally:
        connection.close()


def _decode_json(body: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} did not return valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} JSON must be an object")
    return value


def _check_security_headers(headers: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for name, expected in REQUIRED_SECURITY_HEADERS.items():
        actual = headers.get(name)
        if actual != expected:
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")
    request_id = headers.get("x-request-id", "")
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        failures.append("x-request-id: missing or invalid")
    csp = headers.get("content-security-policy", "")
    if "default-src 'none'" not in csp or "frame-ancestors 'none'" not in csp:
        failures.append("content-security-policy: API deny-by-default policy missing")
    return failures


def run_probe(base_url: str, *, samples: int = 12, timeout: float = 8.0) -> dict[str, Any]:
    if not 3 <= samples <= 100:
        raise ValueError("samples must be between 3 and 100")
    if not 1.0 <= timeout <= 30.0:
        raise ValueError("timeout must be between 1 and 30 seconds")

    parsed = _validate_base_url(base_url)
    host = parsed.hostname
    if host is None:
        raise RuntimeError("validated URL lost hostname")
    port = parsed.port or 443
    resolved_addresses = _resolve_public_addresses(host, port)

    failures: list[str] = []
    checks: dict[str, Any] = {}

    live_status, live_headers, live_body, live_ms = _request(
        parsed, "/health/live", timeout=timeout
    )
    live_json = _decode_json(live_body, "liveness") if live_status == 200 else {}
    if live_status != 200 or live_json.get("status") != "ok":
        failures.append(f"liveness failed: HTTP {live_status}, status={live_json.get('status')!r}")
    header_failures = _check_security_headers(live_headers)
    failures.extend(f"security header: {item}" for item in header_failures)
    checks["liveness"] = {
        "http_status": live_status,
        "status": live_json.get("status"),
        "version": live_json.get("version"),
        "duration_ms": round(live_ms, 3),
        "security_headers_pass": not header_failures,
    }

    ready_status, _ready_headers, ready_body, ready_ms = _request(
        parsed, "/health/ready", timeout=timeout
    )
    ready_json = _decode_json(ready_body, "readiness") if ready_status == 200 else {}
    if ready_status != 200 or ready_json.get("status") != "ready":
        failures.append(f"readiness failed: HTTP {ready_status}, status={ready_json.get('status')!r}")
    checks["readiness"] = {
        "http_status": ready_status,
        "status": ready_json.get("status"),
        "version": ready_json.get("version"),
        "duration_ms": round(ready_ms, 3),
    }

    capability_status, _cap_headers, cap_body, cap_ms = _request(
        parsed, "/v1/meta/capabilities", timeout=timeout
    )
    capabilities = _decode_json(cap_body, "capabilities") if capability_status == 200 else {}
    if capability_status != 200:
        failures.append(f"capabilities failed: HTTP {capability_status}")
    if capabilities.get("generated_answers") is not False:
        failures.append("generated answers must remain disabled on staging evidence runs")
    if capabilities.get("rag") is not False:
        failures.append("RAG generation must remain disabled on staging evidence runs")
    checks["capabilities"] = {
        "http_status": capability_status,
        "api_version": capabilities.get("api_version"),
        "generated_answers": capabilities.get("generated_answers"),
        "rag": capabilities.get("rag"),
        "duration_ms": round(cap_ms, 3),
    }

    bad_host_status, _bad_headers, _bad_body, bad_host_ms = _request(
        parsed,
        "/health/live",
        timeout=timeout,
        host_header="invalid-host.aisearcharab.invalid",
    )
    if bad_host_status not in {400, 404, 421}:
        failures.append(f"invalid Host header was not rejected: HTTP {bad_host_status}")
    checks["host_policy"] = {
        "invalid_host_http_status": bad_host_status,
        "duration_ms": round(bad_host_ms, 3),
        "pass": bad_host_status in {400, 404, 421},
    }

    latency_samples: list[float] = []
    sample_statuses: list[int] = []
    for _ in range(samples):
        status, _headers, _body, duration_ms = _request(
            parsed, "/health/live", timeout=timeout
        )
        sample_statuses.append(status)
        latency_samples.append(duration_ms)
    if any(status != 200 for status in sample_statuses):
        failures.append("one or more latency samples returned a non-200 response")

    latency = {
        "samples": samples,
        "p50_ms": round(_percentile(latency_samples, 0.50), 3),
        "p95_ms": round(_percentile(latency_samples, 0.95), 3),
        "p99_ms": round(_percentile(latency_samples, 0.99), 3),
        "max_ms": round(max(latency_samples), 3),
    }
    checks["latency"] = latency

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "target": {
            "origin": f"https://{host}" + (f":{parsed.port}" if parsed.port else ""),
            "resolved_public_addresses": resolved_addresses,
        },
        "checks": checks,
        "failures": failures,
        "overall_pass": not failures,
    }


def _write_evidence(path: str | Path, evidence: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect fail-closed public AISearcharab staging evidence")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--output", default="/tmp/aisearcharab-staging-evidence.json")
    args = parser.parse_args()

    try:
        evidence = run_probe(args.base_url, samples=args.samples, timeout=args.timeout)
    except Exception as exc:  # Evidence is still emitted for operational diagnosis.
        evidence = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "target": {"origin": args.base_url},
            "checks": {},
            "failures": [f"probe exception: {type(exc).__name__}: {exc}"],
            "overall_pass": False,
        }

    _write_evidence(args.output, evidence)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if evidence["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
