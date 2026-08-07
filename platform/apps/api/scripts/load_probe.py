from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True, slots=True)
class ProbeSummary:
    requests: int
    successes: int
    errors: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile_value / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def summarize(latencies_ms: list[float], *, requests: int, errors: int) -> ProbeSummary:
    successes = requests - errors
    return ProbeSummary(
        requests=requests,
        successes=successes,
        errors=errors,
        error_rate=round(errors / requests if requests else 1.0, 6),
        p50_ms=round(percentile(latencies_ms, 50), 3),
        p95_ms=round(percentile(latencies_ms, 95), 3),
        p99_ms=round(percentile(latencies_ms, 99), 3),
        min_ms=round(min(latencies_ms), 3) if latencies_ms else 0.0,
        max_ms=round(max(latencies_ms), 3) if latencies_ms else 0.0,
    )


def load_queries(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("query file must contain a JSON list")
    queries: list[str] = []
    for row in payload:
        if isinstance(row, str):
            query = row.strip()
        elif isinstance(row, dict) and isinstance(row.get("query"), str):
            query = row["query"].strip()
        else:
            raise ValueError("each query row must be a string or an object containing a string 'query'")
        if not 2 <= len(query) <= 120:
            raise ValueError("each query must contain between 2 and 120 characters")
        queries.append(query)
    if not queries:
        raise ValueError("query file must contain at least one query")
    return queries


def validate_base_url(value: str, *, allow_http: bool) -> str:
    parsed = urlparse(value)
    allowed_schemes = {"https"} | ({"http"} if allow_http else set())
    if parsed.scheme not in allowed_schemes:
        raise ValueError("base URL must use HTTPS unless --allow-http is explicitly supplied")
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("base URL must have a host and must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query string or fragment")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def run_probe(
    *,
    base_url: str,
    queries: list[str],
    request_count: int,
    concurrency: int,
    timeout_seconds: float,
) -> ProbeSummary:
    latencies: list[float] = []
    errors = 0
    endpoint = f"{base_url}/v1/search"

    limits = httpx.Limits(max_connections=max(concurrency * 2, 10), max_keepalive_connections=max(concurrency, 5))
    timeout = httpx.Timeout(timeout_seconds)

    def one_request(client: httpx.Client, index: int) -> tuple[bool, float]:
        query = queries[index % len(queries)]
        started = time.perf_counter()
        try:
            response = client.get(
                endpoint,
                params={"q": query, "limit": 10},
                headers={"Accept": "application/json", "X-Load-Probe": "staging-release-gate"},
            )
            elapsed = (time.perf_counter() - started) * 1000
            return response.status_code == 200, elapsed
        except httpx.HTTPError:
            return False, (time.perf_counter() - started) * 1000

    with httpx.Client(timeout=timeout, limits=limits, follow_redirects=False) as client:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(one_request, client, index) for index in range(request_count)]
            for future in as_completed(futures):
                ok, elapsed = future.result()
                if ok:
                    latencies.append(elapsed)
                else:
                    errors += 1

    return summarize(latencies, requests=request_count, errors=errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a privacy-minimized staging search load probe. The report contains aggregate latency/error metrics only; "
            "query text and response bodies are never printed."
        )
    )
    parser.add_argument("--base-url", required=True, help="API origin or base path, normally the Staging HTTPS URL")
    parser.add_argument("--queries", type=Path, required=True, help="JSON query set; strings or objects with a 'query' field")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-p95-ms", type=float, default=750.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--allow-http", action="store_true", help="Permit HTTP for local development only")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.requests <= 100_000:
        raise SystemExit("--requests must be between 1 and 100000")
    if not 1 <= args.concurrency <= 200:
        raise SystemExit("--concurrency must be between 1 and 200")
    if not 0.1 <= args.timeout_seconds <= 120:
        raise SystemExit("--timeout-seconds must be between 0.1 and 120")
    if args.max_p95_ms <= 0:
        raise SystemExit("--max-p95-ms must be positive")
    if not 0 <= args.max_error_rate <= 1:
        raise SystemExit("--max-error-rate must be between 0 and 1")

    try:
        base_url = validate_base_url(args.base_url, allow_http=args.allow_http)
        queries = load_queries(args.queries)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc

    summary = run_probe(
        base_url=base_url,
        queries=queries,
        request_count=args.requests,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))

    if summary.successes == 0:
        print("load probe failed: no successful responses", file=sys.stderr)
        return 1
    if summary.error_rate > args.max_error_rate:
        print(
            f"load probe failed: error_rate={summary.error_rate} exceeds {args.max_error_rate}",
            file=sys.stderr,
        )
        return 1
    if summary.p95_ms > args.max_p95_ms:
        print(
            f"load probe failed: p95_ms={summary.p95_ms} exceeds {args.max_p95_ms}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
