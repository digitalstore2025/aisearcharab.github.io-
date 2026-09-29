from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from http.client import RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from agent_os.network_faults import ToxiproxyClient
from agent_os.reliability import FailureClass, FailureSignal, RecoveryBudget, RecoveryPolicy
from agent_os.runtime import OperationSpec, RecoveryExecutor

GATE_VERSION = "1.0.0"
EXPECTED_TOXIPROXY_VERSION = "2.12.0"
TOXIPROXY_IMAGE_DIGEST = "sha256:9378ed52a28bc50edc1350f936f518f31fa95f0d15917d6eb40b8e376d1a214e"


class InjectedNetworkFault(RuntimeError):
    pass


class RateLimited(RuntimeError):
    pass


@dataclass
class FixtureState:
    mutations: dict[str, int] = field(default_factory=dict)
    rate_limit_calls: int = 0


class FixtureHandler(BaseHTTPRequestHandler):
    state: FixtureState

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib API
        return

    def _send_json(self, status: int, payload: dict, *, headers: dict[str, str] | None = None) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/state":
            key = parse_qs(parsed.query).get("key", [""])[0]
            self._send_json(200, {"count": self.state.mutations.get(key, 0)})
            return
        if parsed.path == "/rate-limit":
            self.state.rate_limit_calls += 1
            if self.state.rate_limit_calls == 1:
                self._send_json(429, {"error": "rate_limited"}, headers={"Retry-After": "0"})
            else:
                self._send_json(200, {"ok": True, "attempt": self.state.rate_limit_calls})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        parsed = urlsplit(self.path)
        if parsed.path != "/mutate":
            self._send_json(404, {"error": "not_found"})
            return
        key = self.headers.get("Idempotency-Key", "")
        if not key:
            self._send_json(400, {"error": "missing_idempotency_key"})
            return
        self.state.mutations[key] = self.state.mutations.get(key, 0) + 1
        self._send_json(200, {"committed": True, "count": self.state.mutations[key]})


@dataclass(frozen=True)
class ScenarioEvidence:
    passed: bool
    success: bool
    safe_stop: bool
    attempts: int
    tool_calls: int
    verification_calls: int
    actions: tuple[str, ...]
    recovered_by: str | None
    duration_s: float
    mutation_count: int | None = None


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 1.0,
) -> dict:
    request = Request(url, method=method, headers=headers or {"User-Agent": "astra-agent-os-ci"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def _network_call(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, timeout: float = 0.25) -> dict:
    try:
        return _http_json(url, method=method, headers=headers, timeout=timeout)
    except HTTPError:
        raise
    except (TimeoutError, socket.timeout, ConnectionResetError, RemoteDisconnected, URLError, OSError) as exc:
        raise InjectedNetworkFault("network fault") from exc


def _start_fixture() -> tuple[ThreadingHTTPServer, threading.Thread, FixtureState, str]:
    state = FixtureState()

    class BoundHandler(FixtureHandler):
        pass

    BoundHandler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", 0), BoundHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, state, f"http://{host}:{port}"


def _evidence(result, *, duration_s: float, passed: bool, mutation_count: int | None = None) -> ScenarioEvidence:
    return ScenarioEvidence(
        passed=passed,
        success=result.success,
        safe_stop=result.safe_stop,
        attempts=result.attempts,
        tool_calls=result.tool_calls,
        verification_calls=result.verification_calls,
        actions=result.actions,
        recovered_by=result.recovered_by,
        duration_s=round(duration_s, 6),
        mutation_count=mutation_count,
    )


def run_gate(*, source_sha: str, toxiproxy_api: str) -> dict:
    server, thread, state, upstream = _start_fixture()
    toxi = ToxiproxyClient(toxiproxy_api)
    proxy_name = "agent-os-live-gate"
    started = time.monotonic()
    evidence: dict[str, ScenarioEvidence] = {}

    try:
        version = toxi.version()
        if version != EXPECTED_TOXIPROXY_VERSION:
            raise RuntimeError(f"expected Toxiproxy {EXPECTED_TOXIPROXY_VERSION}, got {version}")
        toxi.reset()
        toxi.delete_proxy(proxy_name)
        created = toxi.create_proxy(proxy_name, "127.0.0.1:0", upstream.removeprefix("http://"))
        listen = created.get("listen")
        if not isinstance(listen, str) or not listen.startswith("127.0.0.1:"):
            raise RuntimeError("Toxiproxy did not return a loopback listener")
        proxy_base = f"http://{listen}"

        # 1. Non-atomic failure: request reaches the server and commits, but the
        # downstream response is dropped. The executor must verify state before
        # any replay and therefore keep mutation_count == 1.
        toxi.add_toxic(
            proxy_name,
            name="drop-response",
            toxic_type="timeout",
            stream="downstream",
            attributes={"timeout": 100},
        )
        key = "timeout-after-dispatch"
        executor = RecoveryExecutor(RecoveryPolicy(RecoveryBudget(3, 6, 5)))
        t0 = time.monotonic()
        result = executor.execute(
            OperationSpec("live-nonatomic-mutation"),
            lambda: _network_call(
                f"{proxy_base}/mutate",
                method="POST",
                headers={"Idempotency-Key": key},
                timeout=0.4,
            ),
            lambda exc: FailureSignal(FailureClass.TIMEOUT, side_effect_uncertain=True),
            verify_postcondition=lambda: _http_json(f"{upstream}/state?key={key}", timeout=1).get("count") == 1,
        )
        duration = time.monotonic() - t0
        mutation_count = state.mutations.get(key, 0)
        passed = (
            result.success
            and result.recovered_by == "postcondition_verified"
            and result.tool_calls == 1
            and result.verification_calls == 1
            and mutation_count == 1
        )
        evidence["timeout_after_dispatch"] = _evidence(
            result, duration_s=duration, passed=passed, mutation_count=mutation_count
        )
        toxi.reset()

        # 2. HTTP-level transient: a deterministic 429 clears on the next call.
        state.rate_limit_calls = 0

        def rate_limited_operation():
            try:
                return _http_json(f"{proxy_base}/rate-limit", timeout=1)
            except HTTPError as exc:
                if exc.code == 429:
                    raise RateLimited("rate limited") from exc
                raise

        t0 = time.monotonic()
        result = executor.execute(
            OperationSpec("live-rate-limited-read", idempotent=True),
            rate_limited_operation,
            lambda exc: FailureSignal(FailureClass.RATE_LIMIT, idempotent=True),
        )
        duration = time.monotonic() - t0
        passed = result.success and result.attempts == 2 and result.actions == ("retry",) and state.rate_limit_calls == 2
        evidence["rate_limit_retry"] = _evidence(result, duration_s=duration, passed=passed)

        # 3. Persistent latency: prove retries are finite and terminate safely.
        toxi.add_toxic(
            proxy_name,
            name="persistent-latency",
            toxic_type="latency",
            stream="downstream",
            attributes={"latency": 500, "jitter": 0},
        )
        bounded = RecoveryExecutor(RecoveryPolicy(RecoveryBudget(2, 2, 2)))
        t0 = time.monotonic()
        result = bounded.execute(
            OperationSpec("live-latency-read", idempotent=True),
            lambda: _network_call(f"{proxy_base}/health", timeout=0.05),
            lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
        )
        duration = time.monotonic() - t0
        passed = (
            not result.success
            and result.safe_stop
            and result.attempts == 2
            and result.tool_calls == 2
            and result.actions == ("retry", "escalate")
            and duration < 2.0
        )
        evidence["persistent_latency_budget"] = _evidence(result, duration_s=duration, passed=passed)
        toxi.reset()

        passed_count = sum(item.passed for item in evidence.values())
        report = {
            "gate_version": GATE_VERSION,
            "source_sha": source_sha,
            "transport": "loopback_http_via_toxiproxy",
            "toxiproxy": {
                "version": version,
                "image_digest": TOXIPROXY_IMAGE_DIGEST,
            },
            "summary": {
                "passed": passed_count,
                "total": len(evidence),
                "pass": passed_count == len(evidence),
                "duration_s": round(time.monotonic() - started, 6),
            },
            "scenarios": {name: asdict(item) for name, item in evidence.items()},
            "limitations": [
                "Local CI fault gate; it does not estimate production provider failure rates.",
                "Toxiproxy validates transport-failure behavior, not model reasoning quality.",
                "Production promotion still requires real staging telemetry, external probes, and repository governance.",
            ],
        }
        return report
    finally:
        try:
            toxi.reset()
            toxi.delete_proxy(proxy_name)
        except Exception:
            pass
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--toxiproxy-api", default="http://127.0.0.1:8474")
    args = parser.parse_args()

    report = run_gate(source_sha=args.source_sha, toxiproxy_api=args.toxiproxy_api)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["summary"]["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
