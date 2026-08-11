# AISearcharab — Deployment Contract

## Build and validation

The deployable revision must pass the canonical site/platform workflows and the security-regression workflow. Required commands represented by CI include:

```bash
python -m ruff check src tests scripts alembic
python scripts/validate_secure_source.py
python -m compileall -q src tests scripts alembic
python -m pytest
python scripts/evaluate_search.py
alembic upgrade head
alembic check
docker compose config -q
```

Hugo validation remains in the reusable site workflow before any GitHub Pages upload.

## Runtime topology

- HTTPS public frontend;
- HTTPS API or reviewed same-origin route;
- managed PostgreSQL for staging/production;
- secrets injected by deployment environment/secret manager;
- distributed edge rate limit/WAF before production;
- external logs/metrics/alerts before production.

SQLite and wildcard production hosts/origins are rejected by application configuration.

## Database

Run migrations as a single controlled job before accepting traffic. The current expected schema revision remains `20260808_0005`. `/health/ready` rejects a staging/production database at a different revision.

## Required live probes

```bash
curl --fail --silent --show-error https://<api>/health/live
curl --fail --silent --show-error https://<api>/health/ready
curl --fail --silent --show-error https://<api>/v1/meta/capabilities
curl --fail --silent --show-error -I https://<api>/admin/
```

The header response must expose at least:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: ...
Cache-Control: no-store
X-DNS-Prefetch-Control: off
Strict-Transport-Security: ...
```

## Adversarial runtime probe

An oversized request must return 413 even when the client does not rely on a trusted `Content-Length`. CI sends a body using chunked transfer encoding to prove the streamed ceiling.

The current product exposes no file upload/storage API. `/v1/admin/upload` must remain absent until a separately reviewed storage subsystem exists; CI sends a script-bearing SVG with a spoofed MIME and requires a 404.

## Rollback

Application rollback and database recovery are separate operations. Record the known-good image/commit before rollout. Prefer forward-fix migrations when data-compatible; use the managed database restore procedure for destructive/incompatible incidents. Production approval requires a real restore/rollback drill with measured RPO/RTO.

## Promotion

`INTEGRATED_NOT_TESTED` → `TESTED_IN_STAGING` only after a reachable HTTPS staging deployment passes live probes and privileged MFA/editorial smoke tests. `EXTERNALLY_VERIFIED` requires independent security/accessibility evidence. `PRODUCTION_READY` additionally requires all Issue #14 gates and explicit human approval.
