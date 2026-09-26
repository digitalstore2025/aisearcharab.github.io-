from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import math
import multiprocessing
import re
import socket
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit
from uuid import uuid4

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
DATABASE_BINDING_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{3,128}$")
MAX_RESPONSE_BYTES = 128 * 1024
REQUIRED_SECURITY_HEADERS = {
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
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("staging URL contains an invalid port") from exc
    return parsed


def _safe_origin(raw: str) -> str | None:
    try:
        parsed = _validate_base_url(raw)
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname
    if host is None:
        return None
    return f"https://{host}" + (f":{port}" if port else "")


def _dns_worker(hostname: str, port: int, output: Any) -> None:
    try:
        output.put(("ok", socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)))
    except BaseException as exc:
        output.put(("error", f"{type(exc).__name__}: {exc}"))


def _resolve_public_addresses(hostname: str, port: int, *, timeout: float) -> list[str]:
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(target=_dns_worker, args=(hostname, port, output), daemon=True)
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(1.0)
        output.close()
        raise RuntimeError("staging DNS resolution timed out")
    if output.empty():
        output.close()
        raise RuntimeError("staging DNS resolution failed without a result")
    status, payload = output.get()
    output.close()
    if status != "ok":
        raise RuntimeError(f"staging DNS resolution failed: {payload}")
    records = payload

    addresses: set[str] = set()
    for family, socktype, proto, _canonname, sockaddr in records:
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


def _remaining(deadline: float, message: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(message)
    return remaining


def _request(
    parsed: SplitResult,
    path: str,
    *,
    addresses: list[str],
    timeout: float,
    host_header: str | None = None,
    request_id: str | None = None,
) -> tuple[int, dict[str, str], bytes, float]:
    host = parsed.hostname
    if host is None:
        raise RuntimeError("validated URL lost hostname")
    if not addresses:
        raise RuntimeError("no validated staging addresses available")
    port = parsed.port or 443
    headers = {"Accept": "application/json", "User-Agent": "AISearcharab-Staging-Evidence/1.0"}
    if host_header is not None:
        headers["Host"] = host_header
    if request_id is not None:
        headers["X-Request-ID"] = request_id

    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    failures: list[str] = []
    for address in addresses:
        connection: http.client.HTTPSConnection | None = None
        raw_socket: socket.socket | None = None
        tls_socket: ssl.SSLSocket | None = None
        try:
            connect_timeout = _remaining(deadline, "HTTP request exceeded wall-clock deadline before TCP connect")
            raw_socket = socket.create_connection((address, port), timeout=connect_timeout)

            tls_timeout = _remaining(deadline, "HTTP request exceeded wall-clock deadline before TLS handshake")
            raw_socket.settimeout(tls_timeout)
            context = ssl.create_default_context()
            tls_socket = context.wrap_socket(raw_socket, server_hostname=host)
            raw_socket = None

            request_timeout = _remaining(deadline, "HTTP request exceeded wall-clock deadline before request send")
            tls_socket.settimeout(request_timeout)
            connection = http.client.HTTPSConnection(host, port, timeout=request_timeout, context=context)
            connection.sock = tls_socket
            tls_socket = None
            connection.request("GET", path, headers=headers)

            response_timeout = _remaining(deadline, "HTTP request exceeded wall-clock deadline")
            if connection.sock is None:
                raise RuntimeError("TLS socket unavailable after request")
            connection.sock.settimeout(response_timeout)
            response = connection.getresponse()
            chunks: list[bytes] = []
            total = 0
            while total <= MAX_RESPONSE_BYTES:
                read_timeout = _remaining(deadline, "HTTP response exceeded wall-clock deadline")
                if connection.sock is None:
                    raise RuntimeError("TLS socket unavailable while reading response")
                connection.sock.settimeout(read_timeout)
                chunk = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            body = b"".join(chunks)
            duration_ms = (time.perf_counter() - started) * 1000
            if len(body) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"response body exceeded {MAX_RESPONSE_BYTES} bytes")
            normalized_headers = {key.lower(): value for key, value in response.getheaders()}
            return response.status, normalized_headers, body, duration_ms
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError, RuntimeError) as exc:
            failures.append(f"{address}: {type(exc).__name__}")
            if time.monotonic() >= deadline:
                break
        finally:
            if connection is not None:
                connection.close()
            elif tls_socket is not None:
                tls_socket.close()
            elif raw_socket is not None:
                raw_socket.close()
    raise RuntimeError("all validated staging addresses failed: " + ", ".join(failures))


def _decode_json(body: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} did not return valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} JSON must be an object")
    return value


def _decode_json_evidence(body: bytes, label: str, failures: list[str]) -> dict[str, Any]:
    try:
        return _decode_json(body, label)
    except RuntimeError as exc:
        failures.append(str(exc))
        return {}


def _parse_csp(csp: str) -> tuple[dict[str, list[str]], set[str]]:
    directives: dict[str, list[str]] = {}
    duplicates: set[str] = set()
    for raw_directive in csp.split(";"):
        parts = raw_directive.strip().split()
        if not parts:
            continue
        name = parts[0].lower()
        if name in directives:
            duplicates.add(name)
            continue
        directives[name] = parts[1:]
    return directives, duplicates


def _check_security_headers(headers: dict[str, str], *, expected_request_id: str | None = None) -> list[str]:
    failures: list[str] = []
    for name, expected in REQUIRED_SECURITY_HEADERS.items():
        actual = headers.get(name)
        if actual != expected:
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")
    request_id = headers.get("x-request-id", "")
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        failures.append("x-request-id: missing or invalid")
    elif expected_request_id is not None and request_id != expected_request_id:
        failures.append("x-request-id: response did not preserve the supplied correlation ID")
    directives, duplicates = _parse_csp(headers.get("content-security-policy", ""))
    if duplicates:
        failures.append("content-security-policy: duplicate directives are not accepted")
    if directives.get("default-src") != ["'none'"] or directives.get("frame-ancestors") != ["'none'"]:
        failures.append("content-security-policy: default-src and frame-ancestors must each be exactly 'none'")
    return failures


def run_probe(
    base_url: str,
    *,
    samples: int = 12,
    timeout: float = 8.0,
    expected_revision: str | None = None,
    expected_database_binding: str | None = None,
) -> dict[str, Any]:
    if not 3 <= samples <= 100:
        raise ValueError("samples must be between 3 and 100")
    if not 1.0 <= timeout <= 30.0:
        raise ValueError("timeout must be between 1 and 30 seconds")
    if expected_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_revision.lower()):
        raise ValueError("expected revision must be a full 40-character Git SHA")
    if expected_database_binding is not None and not DATABASE_BINDING_PATTERN.fullmatch(expected_database_binding):
        raise ValueError("expected database binding must be a safe non-secret identifier")

    parsed = _validate_base_url(base_url)
    host = parsed.hostname
    if host is None:
        raise RuntimeError("validated URL lost hostname")
    port = parsed.port or 443
    resolved_addresses = _resolve_public_addresses(host, port, timeout=timeout)
    failures: list[str] = []
    checks: dict[str, Any] = {}

    correlation_id = f"staging-probe-{uuid4()}"
    live_status, live_headers, live_body, live_ms = _request(
        parsed,
        "/health/live",
        addresses=resolved_addresses,
        timeout=timeout,
        request_id=correlation_id,
    )
    live_json = _decode_json_evidence(live_body, "liveness", failures) if live_status == 200 else {}
    if live_status != 200 or live_json.get("status") != "ok":
        failures.append(f"liveness failed: HTTP {live_status}, status={live_json.get('status')!r}")
    header_failures = _check_security_headers(live_headers, expected_request_id=correlation_id)
    failures.extend(f"security header: {item}" for item in header_failures)
    checks["liveness"] = {
        "http_status": live_status,
        "status": live_json.get("status"),
        "version": live_json.get("version"),
        "duration_ms": round(live_ms, 3),
        "security_headers_pass": not header_failures,
    }

    ready_status, _ready_headers, ready_body, ready_ms = _request(
        parsed, "/health/ready", addresses=resolved_addresses, timeout=timeout
    )
    ready_json = _decode_json_evidence(ready_body, "readiness", failures) if ready_status == 200 else {}
    if ready_status != 200 or ready_json.get("status") != "ready":
        failures.append(f"readiness failed: HTTP {ready_status}, status={ready_json.get('status')!r}")
    checks["readiness"] = {
        "http_status": ready_status,
        "status": ready_json.get("status"),
        "version": ready_json.get("version"),
        "duration_ms": round(ready_ms, 3),
    }

    deployment_status, _deployment_headers, deployment_body, deployment_ms = _request(
        parsed, "/v1/meta/deployment", addresses=resolved_addresses, timeout=timeout
    )
    deployment = (
        _decode_json_evidence(deployment_body, "deployment provenance", failures)
        if deployment_status == 200
        else {}
    )
    deployed_revision = str(deployment.get("revision") or "").lower()
    deployed_database_binding = str(deployment.get("database_binding") or "")
    if deployment_status != 200:
        failures.append(f"deployment provenance failed: HTTP {deployment_status}")
    if not re.fullmatch(r"[0-9a-f]{40}", deployed_revision):
        failures.append("deployment provenance did not expose a full immutable Git SHA")
    if not DATABASE_BINDING_PATTERN.fullmatch(deployed_database_binding):
        failures.append("deployment provenance did not expose a valid database binding identity")
    if expected_revision is not None and deployed_revision != expected_revision.lower():
        failures.append(
            f"deployed revision mismatch: expected {expected_revision.lower()}, got {deployed_revision or 'missing'}"
        )
    if expected_database_binding is not None and deployed_database_binding != expected_database_binding:
        failures.append(
            "database binding mismatch: "
            f"expected {expected_database_binding}, got {deployed_database_binding or 'missing'}"
        )
    checks["deployment"] = {
        "http_status": deployment_status,
        "revision": deployed_revision or None,
        "expected_revision": expected_revision.lower() if expected_revision else None,
        "revision_match": bool(expected_revision and deployed_revision == expected_revision.lower()),
        "database_binding": deployed_database_binding or None,
        "expected_database_binding": expected_database_binding,
        "database_binding_match": bool(
            expected_database_binding and deployed_database_binding == expected_database_binding
        ),
        "duration_ms": round(deployment_ms, 3),
    }

    capability_status, _cap_headers, cap_body, cap_ms = _request(
        parsed, "/v1/meta/capabilities", addresses=resolved_addresses, timeout=timeout
    )
    capabilities = _decode_json_evidence(cap_body, "capabilities", failures) if capability_status == 200 else {}
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
        addresses=resolved_addresses,
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
        sample_status, _headers, _body, duration_ms = _request(
            parsed, "/health/live", addresses=resolved_addresses, timeout=timeout
        )
        sample_statuses.append(sample_status)
        latency_samples.append(duration_ms)
    if any(sample_status != 200 for sample_status in sample_statuses):
        failures.append("one or more latency samples returned a non-200 response")
    checks["latency"] = {
        "samples": samples,
        "p50_ms": round(_percentile(latency_samples, 0.50), 3),
        "p95_ms": round(_percentile(latency_samples, 0.95), 3),
        "p99_ms": round(_percentile(latency_samples, 0.99), 3),
        "max_ms": round(max(latency_samples), 3),
    }

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
    parser.add_argument("--expected-revision")
    parser.add_argument("--expected-database-binding")
    parser.add_argument("--output", default="/tmp/aisearcharab-staging-evidence.json")
    args = parser.parse_args()

    try:
        evidence = run_probe(
            args.base_url,
            samples=args.samples,
            timeout=args.timeout,
            expected_revision=args.expected_revision,
            expected_database_binding=args.expected_database_binding,
        )
    except Exception as exc:
        evidence = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "target": {"origin": _safe_origin(args.base_url)},
            "checks": {},
            "failures": [f"probe exception: {type(exc).__name__}: {exc}"],
            "overall_pass": False,
        }

    _write_evidence(args.output, evidence)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0 if evidence["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
