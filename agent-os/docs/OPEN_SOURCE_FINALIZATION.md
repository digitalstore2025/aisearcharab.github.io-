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

## Human approval enforcement

Approval-gated actions are now enforced at the MCP/tool gateway rather than represented only as an `approval_required` status.

- Policy remains deny-by-default.
- A caller-provided boolean is never sufficient to authorize a sensitive action.
- `ApprovalGrant` is bound to the exact action, tool/resource, environment and canonical SHA-256 digest of the tool-call arguments.
- Grants are short-lived and rejected when expired, not-yet-valid, malformed, over the configured TTL, or replayed against changed arguments.
- Authenticity is delegated to an external `ApprovalAuthority` implemented at the deployment boundary, such as an authenticated operator UI, signed approval service, or GitHub Environment gate.
- Prompt-injection blocking executes before approval evaluation; human approval cannot override the untrusted-content boundary.

The core package deliberately does not implement an operator identity provider, approval UI, or credential store. Those are deployment/governance controls and remain external evidence requirements.

## Tools considered but intentionally not added

### Tenacity

Tenacity is a capable Python retry library, but Agent OS intentionally keeps retry semantics inside `RecoveryPolicy`. Adding an independent general retry layer would risk hidden retries that bypass side-effect verification, policy denials, or recovery budgets.

### Chaos Toolkit

Chaos Toolkit is a mature Python chaos-engineering framework and remains suitable for larger infrastructure experiments. It is not required for the current gate because Toxiproxy covers the needed transport failures with a much smaller dependency and attack surface. It can be introduced later for Kubernetes/cloud experiments without changing the core recovery API.

## Final runtime chain

```text
Tool request
  -> MCPGateway
      -> prompt-injection boundary
      -> deny-by-default PolicyEngine
      -> ApprovalEnforcer for approval-gated actions
          -> external ApprovalAuthority
          -> exact call/environment binding
          -> short-lived TTL validation
  -> Tool operation
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

1. Unit tests validate policy, approval-binding and executor invariants.
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
- Approval-gated actions fail closed when no authenticated approval authority is configured.
- Approval is bound to one exact tool call and cannot authorize changed arguments or a different action/environment.
- Approval never bypasses prompt-injection blocking.
- OpenTelemetry is optional and cannot change execution decisions.
- Toxiproxy is CI/test-only and is not a production dependency.

## What is complete in-repository

- deterministic recovery policy;
- executable recovery runtime;
- independent postcondition verification path;
- deny-by-default policy evaluation;
- MCP/tool preflight gateway;
- exact-call approval binding and TTL enforcement;
- external approval-authority interface;
- prompt-injection-before-approval ordering;
- synthetic repeated fault benchmark;
- live network fault gate;
- JSONL observability;
- OpenTelemetry bridge;
- provenance/revision-bound CI evidence;
- immutable Toxiproxy image selection;
- hash-pinned OpenTelemetry CI dependencies.

## External governance boundary

An authenticated human-approval authority/UI, approval revocation or one-time-use persistence, repository branch protection/rulesets, production telemetry retention, and production deployment credentials are environment/administration controls, not application code. They must remain separate evidence gates. The repository must not claim `PRODUCTION_READY` solely because this in-repository finalization passes.
