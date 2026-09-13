# AISearcharab — Implementation Status

Status vocabulary follows the repository release model and is evidence-based. A code path is not marked Production-ready unless the external control is verified with auditable evidence.

## Verified baseline

- `main`: `5038d680300c8039031a0ec2e17500cb6924dda1`
- Public GitHub Pages deploy: workflow run `34736311113` — build and deploy succeeded for the exact baseline SHA.
- Public reader URL: `https://digitalstore2025.github.io/aisearcharab.github.io-/`
- Production-readiness integration candidate: `ops/production-readiness-2026-09-13`

## Integrated engineering controls

- FastAPI modular API with PostgreSQL/Alembic, migration-aware readiness and hardened Docker runtime.
- Opaque admin sessions, CSRF, RBAC, TOTP MFA, step-up authentication, recovery codes and separation-of-duties controls.
- Privacy-preserving distributed login throttling backed by shared database state.
- Arabic lexical retrieval plus reproducible multilingual neural-retrieval research benchmark.
- Human relevance-judgment/adjudication gate for retrieval promotion; the required >=500-query production benchmark is not yet complete.
- Pinned-IP/TLS research transport with SSRF/DNS-rebinding controls.
- Agent OS v2 shadow control plane with default-deny policy, tool/resource binding, Arabic prompt-injection inspection, redacted traces, A/B evaluation and deterministic release packaging.
- Reviewed runtime dependency lock, VEX-aware dependency audit, CycloneDX SBOM, OpenAPI digest pinning and container smoke tests.
- Fail-closed machine-readable release-evidence generator.

## Current staging work

The previous Render preview contract was not valid staging evidence: the broken preview used a missing `requirements.txt`, while the older service resolved mutable dependencies and ran Alembic against SQLite.

The current integration candidate adds:

- a Render-specific runtime adapter that converts Render's managed `postgresql://` connection string to the explicitly reviewed SQLAlchemy `postgresql+psycopg://` dialect without logging credentials;
- a Docker startup path that fails closed when no managed PostgreSQL URL is available;
- `render.yaml` as Infrastructure-as-Code for the existing `aisearcharab-api-staging-v2` service;
- `fromDatabase` wiring to `aisearcharab-staging-db` without committing database credentials;
- Render-generated MFA and login-throttle secrets;
- explicit Staging host/origin allowlists, health check and generated-answer disablement;
- CI-check-gated auto-deploy configuration.

The current Render Postgres instance is a free Staging database and expires on 2026-09-15. It does not satisfy Production HA/PITR/backup/restore requirements.

## Evidence state

| Gate | State |
|---|---|
| Public reader site | PASS |
| Exact-SHA Pages build/deploy | PASS |
| Agent OS shadow control plane | PASS / INTEGRATED |
| Pinned research transport | PASS / INTEGRATED |
| Runtime lock + SBOM/VEX + OpenAPI pin | PASS / INTEGRATED |
| Hardened Docker runtime | PASS / INTEGRATED |
| Neural retrieval research benchmark | PASS as research evidence only |
| >=500-query human-reviewed retrieval benchmark | PENDING |
| Declarative Render Staging contract | IMPLEMENTED_IN_CANDIDATE |
| Managed PostgreSQL Staging wiring | PENDING_BLUEPRINT_SYNC |
| External Staging health/header/Host probes | PENDING |
| Distributed generated-answer rate limiting | PENDING |
| Production observability/SLO evidence | PENDING |
| Managed Production PostgreSQL + PITR + restore drill | BLOCKED_EXTERNAL |
| Branch protection / required checks on `main` | BLOCKED_ADMIN — `main` remains unprotected |
| Independent security review | BLOCKED_EXTERNAL |
| Independent WCAG 2.2 AA/accessibility review | BLOCKED_EXTERNAL |
| Production | BLOCKED |

## Production decision rule

Do not set `PRODUCTION_READY` until `release_evidence.py` has no blockers and every required external control includes an immutable evidence reference. Staging success alone is insufficient for Production promotion.
