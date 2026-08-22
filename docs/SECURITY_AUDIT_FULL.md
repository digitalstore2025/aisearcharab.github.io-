# AISearcharab — Current Security & Reality Audit

Audit date: `2026-08-22`

Verified base: `main@aaa93892a8cad75ec3b9bd418364928690259888`

Hardening branch: `hardening/reality-cleanup-2026-08-22`

Actual repository stack: Hugo/browser JavaScript plus a dynamic `platform/` containing FastAPI/Python 3.12, SQLAlchemy/Alembic, PostgreSQL, Docker Compose, tenant-scoped GEO tooling and controlled local-model provider adapters.

> This document deliberately separates code/CI evidence from external-environment evidence. A green repository workflow is not proof that Production infrastructure exists or is secure.

## Executive classification

- **No claim of `PRODUCTION_READY`.**
- Current code line is eligible only for repository integration testing until Staging/external gates are evidenced.
- The most important live governance blocker is outside the code tree: GitHub currently reports `main` as `protected=false`.
- This hardening branch also removes stale documentation claims, closes Staging configuration gaps, and prevents release-evidence migration drift. Those branch-local fixes remain `PENDING_CI` until the PR workflows complete successfully.

## Findings and controls

| Layer | Problem / attack | Severity | Current evidence | Current disposition |
|---|---|---:|---|---|
| Repository governance | `main` is not protected and required checks are not enforced at the branch layer | **Critical** | Live GitHub branch API reports `protected=false`; Issue #65 remains open; PR #66 intentionally fails closed until protection exists | **EXTERNAL_BLOCKED** — enable Branch Protection/Ruleset; do not simulate this in code |
| Documentation / operational truth | Root README described Backend/Auth/DB as absent even though `platform/` implements them | Medium governance risk | Current source contains FastAPI, PostgreSQL/Alembic, Admin/Auth/MFA/GEO | **FIXED_IN_BRANCH_PENDING_CI** |
| Documentation / SSRF model | Previous audit claimed there was no `urllib/urlopen` outbound path | Medium governance risk | `geo/providers/ollama.py` performs a controlled outbound call to a configured Ollama endpoint | **FIXED_IN_BRANCH_PENDING_CI** — audit now describes the real surface |
| Staging configuration | Staging could accept HTTP CORS origins | High if treated as release-equivalent Staging | `secure_cookies` already treats Staging as secure, while prior origin validation required HTTPS only in Production | **FIXED_IN_BRANCH_PENDING_CI** — Staging and Production now require HTTPS origins |
| Staging database parity | Staging could validate with SQLite | High release-integrity risk | Production architecture requires PostgreSQL-family Staging; prior code rejected SQLite only in Production | **FIXED_IN_BRANCH_PENDING_CI** — SQLite rejected in Staging and Production |
| Staging host policy | Staging could validate with wildcard hosts | High | Prior wildcard-host rejection was Production-only | **FIXED_IN_BRANCH_PENDING_CI** — wildcard hosts rejected in Staging and Production |
| Staging placeholder credentials | Staging could pass configuration with `change-me` embedded in `DATABASE_URL` | High operational risk | Prior placeholder check was Production-only | **FIXED_IN_BRANCH_PENDING_CI** |
| Release evidence | Manual/local release evidence defaulted to migration `20260808_0005` while readiness/CI use `20260816_0008` | Medium integrity risk | `main.py` expects `20260816_0008`; canonical workflow overrides to that revision, but script default was stale | **FIXED_IN_BRANCH_PENDING_CI** with regression test binding default evidence to runtime readiness revision |
| Authentication | Session fixation | High if present | Login creates fresh random session/CSRF secrets; only digests are persisted | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| Authentication | Unauthenticated account-lockout DoS / brute force | High | Pre-auth throttle key is HMAC(source, account); failures are persisted; global account failure counter is not mutated by ordinary pre-auth failures | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY**; distributed edge limits still external |
| Trusted proxies | Spoofed or duplicate `X-Forwarded-For` | High | `TRUSTED_PROXY_CIDRS` is explicit/fail-closed; duplicate header fields are flattened in wire order; nearest untrusted hop selected from trusted chain | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| MFA | Privileged MFA bypass | High | Owner/admin/publisher require completed MFA when configured; Staging/Production require privileged-MFA configuration and encryption key | **IMPLEMENTED_IN_CODE; STAGING_VERIFICATION_PENDING** |
| MFA replay | Reuse of accepted TOTP / recovery codes | High | Counter/recovery state is persisted and concurrency regression coverage exists | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| CSRF | Cross-site privileged mutations | High | SameSite=Strict cookies plus CSRF token binding; privileged/sensitive routes use CSRF and step-up dependencies | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| Authorization | IDOR/BOLA / cross-tenant access | High | RBAC and tenant access checks are server-side; GEO project/query paths scope organization/project/query-set identifiers | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY**; PostgreSQL RLS is not claimed |
| Request handling | Chunked/streamed request-body limit bypass | High | ASGI middleware buffers only up to a configured hard ceiling and rejects overage | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| Browser execution | DOM XSS / dynamic-code sinks in privileged JS | High if present | Security regression scanning rejects dangerous HTML/dynamic execution patterns; admin CSP is restrictive | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| Browser policy | Public caching/framing/content sniffing of admin/API | Medium | `no-store`, CSP, frame denial, `nosniff`, no-referrer, Permissions-Policy, COOP/CORP and HSTS in secure environments | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| SSRF / outbound providers | Internal model adapter pivots to arbitrary network targets | High | Ollama adapter accepts only configured allowlisted hosts (`ollama`, loopback by default), port 11434 by default, forbids credentials/path/query/fragment, rejects redirects, bounds timeout and response size | **CONSTRAINED_CURRENT_SURFACE** — no arbitrary user-supplied URL fetch is established by current code evidence |
| External fetching | Future crawler/source fetch introduces arbitrary URL retrieval | High future risk | Current public source metadata storage is not a general crawler | **NOT_IMPLEMENTED / DESIGN REQUIRED BEFORE EXPOSURE** |
| Database | Direct browser/service-role DB bypass | High if present | DB credentials remain server-side; no direct browser DB surface is claimed | **CURRENT BOUNDARY ACCEPTED** |
| Database | PostgreSQL RLS absent | Medium defense-in-depth | Authorization boundary is API RBAC/tenant checks; RLS is not claimed | **ACCEPTED_ARCHITECTURE_LIMIT** — becomes blocker if direct client DB access is introduced |
| Files/storage | Malicious upload/MIME polyglot | N/A current surface | No application upload/storage endpoint is part of the current runtime contract | **NOT_EXPOSED**; separate design required before adding uploads |
| Supply chain | Dependency/action compromise | High | Python graph digest, `pip-audit --require-hashes --strict`, VEX-aware audit, CycloneDX SBOM, SHA-pinned Actions and digest-pinned container images are present in canonical CI | **IMPLEMENTED_AND_TESTED_IN_REPOSITORY** |
| Secrets | Credentials committed to tree/history | Critical if present | Working-tree and reachable-history scans are release gates; checkout credentials are not persisted | **CI-GATED**; never treat scanner success as proof that external secret management exists |
| Edge abuse controls | Distributed brute force/search/resource abuse | High | Application-level controls exist; no live WAF/distributed edge evidence is attached | **EXTERNAL_BLOCKED** |
| Production database | PITR/backups/restore/least privilege/TLS | High operational | Architecture requires them, but repository CI cannot prove a managed live database or restore drill | **EXTERNAL_BLOCKED** |
| Observability | No externally verified alerting/incident path | Medium/High operational | Privacy-minimized structured request logs exist in application code | **EXTERNAL_BLOCKED** for aggregation, alerts, uptime and incident drill |
| Accessibility | Repository tests mistaken for independent WCAG proof | Medium release-integrity | Semantic/accessibility checks exist, but independent/manual AT verification is not complete | **EXTERNAL_BLOCKED** for final WCAG claim |

## Current Ollama SSRF boundary

The current outbound-network statement is intentionally narrow:

- The Ollama provider is **not** a generic fetch proxy.
- Its endpoint is configuration-controlled, not supplied by a public request parameter.
- Default hosts are restricted to `ollama`, `localhost`, and `127.0.0.1`.
- Default port is `11434`.
- URL credentials, extra path, query and fragment are rejected during provider construction.
- HTTP redirects are rejected rather than followed.
- Response size and request timeout are bounded.

This is materially different from the previous audit statement that no outbound `urllib` path existed. Future additions that resolve arbitrary domains, follow redirects, fetch user-provided URLs or accept configurable wide host allowlists require a fresh SSRF threat model including private/link-local ranges and DNS rebinding.

## Production blockers that cannot be “cleaned away” in source code

The following controls need real environment evidence; replacing them with booleans, mocks or documentation would be unrealistic:

1. GitHub Branch Protection/Ruleset on `main` with required checks and no routine bypass.
2. HTTPS Staging with the intended ingress/forwarding configuration.
3. WAF and distributed rate limiting with observed 429 behavior.
4. Managed PostgreSQL with TLS, backups, PITR and a successful restore drill.
5. External secret injection/rotation procedure.
6. Real Arabic retrieval benchmark and load/SLO evidence.
7. External observability, alert routing and incident drill.
8. Independent security and accessibility review.
9. Rollback verification against the exact release artifact and schema strategy.
10. Explicit human GO for Production.

## Status vocabulary

Use only evidence-backed states:

- `NOT_STARTED`
- `DESIGNED`
- `IMPLEMENTED_NOT_INTEGRATED`
- `INTEGRATED_NOT_TESTED`
- `TESTED_IN_STAGING`
- `EXTERNALLY_VERIFIED`
- `BLOCKED`
- `PRODUCTION_READY`

No document title containing words such as “Perfect”, “Master”, “Ultimate”, or “Hardened” overrides these evidence states.
