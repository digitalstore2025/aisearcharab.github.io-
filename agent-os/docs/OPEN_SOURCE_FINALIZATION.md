# Open-source finalization

## Goal

Finish the Agent OS reliability path with real executable controls instead of prompt-only guidance or synthetic evidence alone.

## Selected open-source components

### Shopify Toxiproxy 2.12.0

- Project: https://github.com/Shopify/toxiproxy
- License: MIT
- CI image: `ghcr.io/shopify/toxiproxy@sha256:9378ed52a28bc50edc1350f936f518f31fa95f0d15917d6eb40b8e376d1a214e`
- Scope: deterministic network fault injection in CI only.
- Security boundary: Agent OS accepts only a loopback Toxiproxy control-plane URL; it cannot be pointed at arbitrary remote destinations.

The live gate uses real TCP/HTTP transport faults for timeout-after-dispatch and persistent latency, then checks Agent OS recovery behavior against observable end state.

### OpenTelemetry Python 1.45.0

- Project: https://github.com/open-telemetry/opentelemetry-python
- License: Apache-2.0
- Optional dependency only; the Agent OS core stays dependency-free.
- API/SDK versions are pinned to `1.45.0`.
- CI verification dependencies are installed from `requirements-otel.txt` with SHA-256 hashes.
- Scope: standard trace emission for sanitized recovery/control metadata.

OpenTelemetry is not allowed to bypass the existing trace allowlist. JSONL and OpenTelemetry sinks consume the same `sanitize_trace_data` function.

## Tools considered but intentionally not added

### Tenacity

Tenacity is a capable Python retry library, but Agent OS intentionally keeps retry semantics inside `RecoveryPolicy`. Adding an independent general retry layer would risk hidden retries that bypass side-effect verification, policy denials, or recovery budgets.

### Chaos Toolkit

Chaos Toolkit is a mature Python chaos-engineering framework and remains suitable for larger infrastructure experiments. It is not required for the current gate because Toxiproxy covers the needed transport failures with a much smaller dependency and attack surface. It can be introduced later for Kubernetes/cloud experiments without changing the core recovery API.

## Final runtime chain

```text
Tool operation
  -> RecoveryExecutor
      -> structured FailureSignal
      -> RecoveryPolicy
          -> retry | verify-before-retry | repair | refresh | replan | escalate | abstain
      -> postcondition verifier before any ambiguous replay
      -> finite attempts/tool/time budgets
  -> payload-minimized trace sanitizer
      -> JSONL
      -> optional OpenTelemetry
```

## Evidence layers

1. Unit tests validate policy and executor invariants.
2. Static fault benchmark compares no-recovery, retry-only, bounded recovery, and bounded recovery + verifier.
3. Live loopback gate runs real transport faults through the immutable Toxiproxy image.
4. OpenTelemetry integration test proves sanitized attributes reach a real SDK exporter.
5. CI uploads revision-bound JSON evidence artifacts.

These layers are cumulative. A green synthetic benchmark never substitutes for a live gate, and a green local live gate never substitutes for staging/production observability.

## Live gate scenarios

### Timeout after dispatch

A side-effecting POST reaches the fixture and commits, but the downstream response is dropped by Toxiproxy. Agent OS must choose `verify_before_retry`. The postcondition probe confirms the mutation exists, returns success, and proves the mutation count remains exactly one.

### HTTP 429

The first request returns 429 and the next succeeds. Because the operation is idempotent, Agent OS performs one bounded retry and then completes.

### Persistent latency

Toxiproxy adds latency greater than the caller timeout. Agent OS retries only within the configured budget and then exits through a safe escalation state. Infinite retry is a test failure.

## Security invariants

- No arbitrary remote Toxiproxy control plane.
- No raw exception message, prompt, credential, request body, or tool output in recovery telemetry.
- No retry after policy denial.
- No blind retry after uncertain external side effect.
- A postcondition probe is an observation and never counts as permission to repeat an irreversible operation unless replay safety is explicitly declared.
- Retry/time/tool budgets are hard boundaries.
- OpenTelemetry is optional and cannot change execution decisions.
- Toxiproxy is CI/test-only and is not a production dependency.

## What is complete in-repository

- deterministic recovery policy;
- executable recovery runtime;
- independent postcondition verification path;
- synthetic repeated fault benchmark;
- live network fault gate;
- JSONL observability;
- OpenTelemetry bridge;
- provenance/revision-bound CI evidence;
- immutable Toxiproxy image selection;
- hash-pinned OpenTelemetry CI dependencies.

## External governance boundary

Repository branch protection/rulesets and production deployment credentials are GitHub/environment administration controls, not application code. They must remain separate evidence gates. The repository must not claim `PRODUCTION_READY` solely because this in-repository finalization passes.
