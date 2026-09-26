# Staging load/SLO evidence contract

This document defines a deliberately bounded staging performance gate for AISearcharab. It is evidence for runtime behavior under a small, reproducible read-only workload. It is **not** a production-capacity claim, stress test, soak test, or authorization to increase traffic against the public service.

## Safety envelope

The GitHub Actions workflow is intentionally fixed to:

- origin: `https://aisearcharab-api-staging-v2.onrender.com`;
- endpoint under load: `GET /v1/search`;
- query fixture: `الذكاء الاصطناعي`;
- total requests: `40`;
- concurrency: `4`;
- per-request global timeout: `8s`;
- generated answers: disabled;
- writes: none;
- credentials: none;
- arbitrary workflow targets: not supported.

The workload starts only after the existing fail-closed staging preflight verifies HTTPS/public DNS, health/readiness, hardened response headers, Host policy, immutable Git revision, the expected `aisearcharab-staging-db-v2` binding, and disabled generated-answer/RAG capability.

## Staging SLO smoke budgets

A run passes only when all 40 search requests complete with no transport or HTTP/application-contract error and the observed network timings satisfy:

| Metric | Budget |
|---|---:|
| Error rate | `0%` |
| p95 | `<= 2500 ms` |
| p99 | `<= 5000 ms` |
| Maximum | `<= 8000 ms` |

The artifact also records p50, throughput, status counts, error categories, and application-reported `took_ms` percentiles.

## Evidence semantics

Passing this workflow proves only that the exact staging revision/database binding satisfied this bounded workload at the time recorded in the JSON artifact. It does not prove:

- production capacity or autoscaling behavior;
- sustained/soak stability;
- peak concurrency limits;
- multi-region latency;
- failover behavior;
- paid production database performance;
- backup/restore readiness;
- third-party dependency capacity;
- generated-answer or LLM performance.

Production readiness therefore remains blocked until representative capacity/load evidence is collected on the intended production-class infrastructure together with recovery, observability, security, accessibility, and governance evidence.

## Execution

Run the manual GitHub Actions workflow `Staging load SLO evidence` only after the intended staging deployment is live. Supply the full 40-character Git SHA expected on Render. The workflow preserves its JSON artifact even on failure and fails closed when the preflight or SLO gate does not pass.
