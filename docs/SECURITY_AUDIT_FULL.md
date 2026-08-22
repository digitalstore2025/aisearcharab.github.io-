# AISearcharab — Current Security & Reality Audit

Audit date: `2026-08-22`

Initial audit base: `main@aaa93892a8cad75ec3b9bd418364928690259888`

Current PR base after synchronization: `main@8735d10b96e9b74e4e9ba794ec5bae1349a627a2`

Hardening branch: `hardening/reality-cleanup-2026-08-22` (PR #68)

Actual repository stack: Hugo/browser JavaScript plus a dynamic `platform/` containing FastAPI/Python 3.12, SQLAlchemy/Alembic, PostgreSQL, Docker Compose, tenant-scoped GEO tooling and controlled local-model provider adapters.

> This document deliberately separates code/CI evidence from external-environment evidence. A green repository workflow is not proof that Production infrastructure exists or is secure. Every push changes the PR head and invalidates earlier CI/review evidence until the new head is verified.

## Executive classification

- **No claim of `PRODUCTION_READY`.**
- Repository-level fixes in PR #68 are accepted only after all required workflows and review threads are clean on the same current head SHA.
- The most important live governance blocker is outside the code tree: the latest verified GitHub branch evidence reports `main` as `protected=false`.
- Staging/Production infrastructure, WAF/distributed rate limits, managed-database recovery, external observability and independent security/accessibility evidence remain external gates; they cannot be converted into “done” states by source edits or CI booleans.

## Findings and controls

| Layer | Problem / attack | Severity | Current evidence | Current disposition |
|---|---|---:|---|---|
| Repository governance | `main` is not protected and required checks are not enforced at the branch layer | **Critical** | Live GitHub branch evidence reports `protected=false`; Issue #65 remains open; PR #66 intentionally fails closed until protection exists | **EXTERNAL_BLOCKED** — enable Branch Protection/Ruleset; do not simulate this in code |
| Documentation / operational truth | Root README described Backend/Auth/DB as absent even though `platform/` implements them | Medium governance risk | Current source contains FastAPI, PostgreSQL/Alembic, Admin/Auth/MFA/GEO | **FIXED_IN_PR** — acceptance requires current-head CI/review |
| Documentation / SSRF model | Previous audit claimed there was no `urllib/urlopen` outbound path | Medium governance risk | `geo/providers/ollama.py` performs a controlled outbound call to a configured Ollama endpoint | **FIXED_IN_PR** — audit now describes the real surface |
| Staging configuration | Staging could accept HTTP CORS origins | High if treated as release-equivalent Staging | Secure cookies already treated Staging as secure while previous origin validation required HTTPS only in Production | **FIXED_IN_PR** — Staging and Production require HTTPS origins; current-head tests required |
| Staging database parity | Staging could validate with SQLite | High release-integrity risk | Production architecture requires PostgreSQL-family Staging; previous code rejected SQLite only in Production | **FIXED_IN_PR** — SQLite rejected in Staging and Production |
| Staging host policy | Staging/Production could validate wildcard host patterns such as `*.example.com` | High | `TrustedHostMiddleware` treats wildcard-subdomain patterns as wildcards; an exact-`*` check was insufficient | **FIXED_IN_PR** — secure runtimes reject any `*` in allowed hosts; regression coverage added |
| Staging placeholder credentials | Staging could pass configuration with `change-me` embedded in `DATABASE_URL` | High operational risk | Previous placeholder check was Production-only | **FIXED_IN_PR** |
| Staging runbook | Required environment omitted `LOGIN_THROTTLE_KEY` and migration checks stopped at `20260808_0005` | High operational/release-integrity risk | Runtime requires the throttle key in Staging/Production and readiness expects `20260816_0008` | **FIXED_IN_PR** — runbook now covers required secret and revisions `0006`–`0008` |
| Release evidence | Default evidence used stale migration `20260808_0005` | Medium integrity risk | Runtime readiness and canonical workflow use `20260816_0008` | **FIXED_IN_PR** — default aligned and regression-bound to runtime readiness revision |
| Release evidence | `PRODUCTION_READY` evidence could override `RELEASE_MIGRATION` to a stale/arbitrary revision | **High release-integrity risk** | Previous validation did not compare final evidence migration with the authoritative current revision | **FIXED_IN_PR** — `PRODUCTION_READY` now rejects mismatched schema revision |
| Supply-chain integration | FastAPI 0.141.1 merged while the reviewed runtime dependency-graph digest remained stale | High integrity/availability risk | CI failed closed on digest mismatch; the newly generated graph digest was then subjected to strict dependency audit/SBOM gates | **FIXED_IN_PR** — updated digest is not accepted unless current-head graph verification/audit/container gates pass |
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
| Supply chain | Dependency/action compromise | High | Python graph digest, `pip-audit --require-hashes --strict`, VEX-aware audit, CycloneDX SBOM, SHA-pinned Actions and digest-pinned container images are present in canonical CI | **CI-GATED** — only current-head success counts |
| Secrets | Credentials committed to tree/history | Critical if present | Working-tree and reachable-history scans are release gates; checkout credentials are not persisted | **CI-GATED**; scanner success is not proof that external secret management exists |
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

## Acceptance rule for PR #68

No earlier green run may be reused after a push. The repository-level hardening in this audit is accepted only when the same current PR head has all required site/API/security/container/release-evidence workflows green and no unresolved actionable review thread. External blockers above remain blockers even when repository CI is fully green.

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
