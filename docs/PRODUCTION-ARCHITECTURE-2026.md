# AISearcharab.com — Production Architecture 2026

Status: `DESIGNED` for external infrastructure. This document is normative for Staging/Production but does not prove that the external environment exists.

## 1. Runtime topology

```text
Internet
  |
  v
DNS / TLS
  |
  v
Edge / WAF / distributed rate limiting
  |                     \
  |                      -> static Hugo frontend/CDN
  v
API ingress
  |
  v
Immutable FastAPI container(s)
  |
  +--> Managed PostgreSQL (TLS, PITR, backups)
  |
  +--> External secret injection / secret manager
  |
  +--> OpenTelemetry exporter
            |
            +--> logs
            +--> metrics
            +--> traces
            +--> alerts
```

## 2. Non-negotiable boundaries

- Production API is containerized and deployed from an immutable, reviewed artifact; do not rebuild a different source after Staging verification.
- Database migrations run as a controlled single-writer release step before/with application rollout. Application replicas do not race to run migrations at startup.
- PostgreSQL must be managed or operated with equivalent production controls: TLS, restricted network access, least-privilege role, automated backups, PITR and a tested restore path.
- Secrets never live in Git, container layers, Hugo output, CI artifacts or application logs.
- Privileged roles (`owner`, `admin`, `publisher`) require MFA in Staging/Production. Password step-up remains a separate defense-in-depth control.
- Distributed rate limiting must exist before traffic reaches expensive/authentication paths. Application-local controls alone are insufficient as the production perimeter.
- `/admin`, authentication and personalized responses are never cached as public content.
- Public frontend and public API may use caching only with endpoint-specific policies.

## 3. Staging parity

Staging must use the same application image, migration mechanism, PostgreSQL engine family, MFA requirement, TLS/secure-cookie policy, secret-injection model, edge policy classes and observability pipeline intended for Production. Reduced capacity is acceptable; weakened security semantics are not.

No SQLite, fake authentication, mocked database or placeholder WAF may be used as evidence for external release gates.

## 4. Edge controls

The selected provider must implement and demonstrate:

- TLS termination and HTTP→HTTPS redirect.
- Canonical host enforcement.
- WAF baseline rules.
- Distributed limits for login, MFA verification/enrollment, password step-up, search and admin mutations.
- 429 behavior for throttled requests.
- Request/body limits compatible with the API's server-side ceiling.
- Explicit forwarding policy; do not trust arbitrary client-supplied forwarding headers.

Exact provider syntax belongs in a provider-specific deployment document after a provider is selected.

## 5. PostgreSQL production contract

Required capabilities:

- PostgreSQL compatible with the tested application/migrations.
- TLS required in transit.
- Dedicated least-privilege application role.
- Separate administrative/migration authority where practical.
- Connection pool and server connection limits.
- Statement/transaction timeout policy appropriate to search/editorial operations.
- Automated backup retention.
- Point-in-time recovery.
- Restore into an isolated environment followed by application integrity/smoke checks.

A configured backup without a successful restore drill does not close the database release gate.

## 6. Secret management contract

Secrets include at least database credentials, `MFA_ENCRYPTION_KEY`, query HMAC key when enabled and any future provider credentials.

Requirements:

- injected at runtime from the hosting environment or secret manager;
- scoped by environment;
- inaccessible to public frontend builds;
- excluded from logs and release evidence;
- rotatable with documented procedure;
- rotation of the MFA encryption key requires an explicit migration/re-encryption design before execution.

## 7. Observability contract

Application telemetry must preserve the project's minimization policy. The external pipeline must prove:

- structured logs are ingested;
- request IDs correlate application events without recording raw query strings, cookies, Authorization headers or bodies;
- request latency/error metrics exist;
- database/resource saturation signals are visible;
- authentication/rate-limit anomalies can alert without leaking credentials;
- a synthetic alert reaches the intended recipient and is handled using the incident runbook.

OpenTelemetry-compatible export is preferred to avoid provider lock-in; the backend may be selected later.

## 8. Release and rollback

```text
reviewed commit
  -> CI/security gates
  -> immutable release artifact
  -> Staging deploy
  -> migrations
  -> live smoke + security + accessibility + load evidence
  -> external verification
  -> explicit human GO
  -> deploy exact approved artifact
  -> post-deploy checks
```

Application rollback and database recovery are separate decisions. Do not automatically downgrade Alembic migrations against valuable data. Prefer a safe forward fix unless the migration has an explicitly tested reversible path.

## 9. Production readiness evidence

`PRODUCTION_READY` requires machine-readable `release-evidence.json` plus human-verifiable evidence attached to Issue #14. In particular CI success alone cannot prove:

- real DNS/TLS;
- external Staging;
- WAF/distributed rate limiting;
- managed PostgreSQL/PITR;
- restore drill;
- observability/alerts;
- real Arabic search quality/load behavior;
- manual accessibility/security verification;
- rollback drill;
- repository branch/ruleset governance.

Until those are demonstrated, the external-environment status remains below `PRODUCTION_READY`.
