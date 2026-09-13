# AISearcharab — Implementation Status

Status vocabulary is evidence-based. Code presence, a mergeable pull request, or a local test result does not prove Production readiness.

## Audit baseline

- Baseline date: `2026-09-05`
- Baseline `main`: `9c2e7d0c1d19a590ab332713f2dce1fa24727593`
- Active audit branch: `audit/training-case-001-2026-09-05`
- Live GitHub branch state at baseline: `main protected=false`
- Production state: `BLOCKED`

## Implemented in repository code

### Static/public layer

- Hugo static-first Arabic/RTL site.
- Structured sources, claims, entities and correction workflows.
- Static Arabic search and generated-site validation.
- Schema.org, canonical, sitemap, robots, RSS and PWA assets.
- Secret/history scanning, project-identity checks and static performance budgets.

### Dynamic platform layer

- FastAPI modular monolith under `platform/`.
- PostgreSQL + Alembic and Arabic PostgreSQL FTS.
- Opaque HttpOnly sessions, CSRF, RBAC, privileged MFA and password step-up.
- Editorial workflow with provenance and concurrency controls.
- Optional grounded generated answers with reviewed-claim/citation constraints and provider provenance.
- Same-origin admin and authenticated assistant surfaces.
- request-size, trusted-host, browser security-header and privacy-minimized telemetry controls.
- dependency graph pinning, strict dependency audit, SBOM and hardened container/release-evidence checks in CI.

### Readiness controls

- Fail-closed readiness guardian exists and its dependency set is hash-pinned.
- This audit pins the guardian's GitHub Actions dependencies to immutable commit SHAs and disables persisted checkout credentials.
- This audit adds a branch-governance workflow that intentionally fails while GitHub reports `main protected=false`.

## Evidence state for this audit branch

| Gate | State | Evidence rule |
|---|---|---|
| Audit changes written | IMPLEMENTED_NOT_INTEGRATED | Branch contains the bounded audit changes |
| Root capability documentation | IMPLEMENTED_NOT_INTEGRATED | README aligned with current platform code |
| Readiness Actions pinning | IMPLEMENTED_NOT_INTEGRATED | Immutable action SHAs on audit branch |
| Branch-governance workflow | IMPLEMENTED_NOT_INTEGRATED | Must fail while live `main` is unprotected |
| Repository CI on audit head | PENDING_CI | Requires GitHub Actions on the final PR head |
| Branch protection / Ruleset | BLOCKED_EXTERNAL | Live GitHub state must become `protected=true` |
| External HTTPS Staging | BLOCKED_EXTERNAL | Requires real runtime evidence |
| Distributed rate limiting/WAF | BLOCKED_EXTERNAL | Requires deployed infrastructure evidence |
| Managed PostgreSQL/PITR/restore | BLOCKED_EXTERNAL | Requires backup/restore drill evidence |
| External observability | BLOCKED_EXTERNAL | Requires deployed telemetry/alerting evidence |
| Real Arabic benchmark/load evidence | BLOCKED_EXTERNAL | Requires representative tasks/users and Staging runs |
| Independent security review | BLOCKED_EXTERNAL | Requires independent reviewer evidence |
| Independent WCAG/browser review | BLOCKED_EXTERNAL | Requires real browser/accessibility evidence |
| Rollback verification | BLOCKED_EXTERNAL | Requires Staging/production-like drill |
| Production | BLOCKED | Cannot pass while critical external gates remain |

## Mandatory next checks

1. Run all workflows triggered by this pull request on one final head SHA.
2. Do not weaken `branch-governance` because it fails; configure GitHub Branch Protection/Ruleset instead.
3. Re-check the live branch object after governance configuration.
4. Keep generated-answer Production activation disabled until its independent runtime gates pass.
5. Update this file only from current evidence; never copy historical PASS states onto a new head without revalidation.
