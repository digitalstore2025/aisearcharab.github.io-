# AISearcharab.com — Perfect Master 2026

## Purpose

This document is the engineering, governance, search-quality, security and launch paper for the 2026 production-readiness line. It defines what is implemented in code, what is externally required, and which claims are forbidden until they are independently verified.

The word **Perfect** in the document title is a project label, not an evidence state. It must never be interpreted as “no defects” or `PRODUCTION_READY`.

## Current release line

Verified repository baseline at the start of the 2026-08-22 reality cleanup: `main@aaa93892a8cad75ec3b9bd418364928690259888`.

The repository now contains more than the original Phase 3.1 retrieval foundation: tenant-scoped GEO measurement/evidence code and constrained Ollama/GPT-OSS provider adapters also exist. These are internal evaluation/inference capabilities. The **public retrieval API remains retrieval-oriented** and there is no evidence-backed claim of a public RAG/vector/generated-answer product surface, general crawler or payments system.

Any future commit, branch or PR must be evaluated against its own CI/evidence. A historical baseline SHA is not proof that later changes passed the same gates.

## 1. Editorial integrity model

The production workflow is designed around three distinct duties:

1. Creator — authors or materially edits the item.
2. Reviewer — verifies sources/claims and approves review state.
3. Publisher — performs the final publication transition.

When `ENFORCE_SEPARATION_OF_DUTIES=true`, the same identity must not perform consecutive governance roles. Production configuration refuses to start unless this control is enabled.

Each content record carries an optimistic revision counter plus creator/reviewer/publisher actor IDs. Critical workflow mutations additionally use database row locks. Publication locks claims before evaluating publication invariants. The goal is to prevent stale-session and concurrent-request races from publishing content whose review has been invalidated.

## 2. Authentication/session baseline

- Opaque random session secrets; only digests are stored.
- HttpOnly session cookies, Strict SameSite, Secure cookies in staging/production.
- CSRF validation for mutations.
- Absolute session TTL plus server-side idle timeout.
- Security-sensitive user changes revoke active sessions.
- Password hashes are versioned and transparently rehashed after successful authentication when their work profile is obsolete.
- TOTP MFA plus recovery-code/replay controls are implemented for privileged accounts and required by staging/production configuration.
- Password step-up is implemented for sensitive mutations and remains distinct from MFA.
- Pre-auth login abuse uses a persisted HMAC(source, account) throttle; trusted forwarding headers are used only when the direct peer belongs to explicitly configured trusted proxy CIDRs.

External production requirement: distributed rate limiting and bot/WAF controls remain mandatory for login/MFA/admin/search. Implemented MFA and login throttling still require real Staging verification; source code alone is not proof that edge policy, secrets delivery or proxy configuration are correct in deployment.

## 3. Search architecture — 2026 retrieval baseline

The public search API remains retrieval-only.

### Candidate retrieval

Production PostgreSQL uses a GIN-backed Arabic-normalized `to_tsvector('simple', ...)` index to select a bounded candidate set before application ranking. `SEARCH_CANDIDATE_LIMIT` is bounded and defaults to 300. CI seeds an Arabic document with hamza/diacritic variants and verifies both application retrieval and index integrity against PostgreSQL.

### Ranking

The current transparent lexical ranker combines:

- exact title match;
- title phrase match;
- field-weighted token coverage;
- protected technical entities;
- source-authority weighting;
- bounded freshness boost;
- deterministic tie-breaking.

### Required evaluation before launch

A real Arabic benchmark must replace the tiny synthetic fixture as launch evidence. Minimum target: 100 human-reviewed queries for development diagnosis; final `PRODUCTION_READY` evidence requires the stricter machine-readable release-evidence threshold of at least 500 queries. The dataset should cover MSA, dialects, mixed Arabic/English, misspellings, technical product names and navigational/informational intent.

Report at least:

- MRR@10;
- NDCG@10;
- Recall@5 / Recall@10;
- Precision@5;
- zero-result rate;
- P50/P95/P99 search latency;
- segment-level metrics by query class.

A perfect score on a small fixture must never be marketed as evidence of production search quality.

## 4. Database and migration discipline

- Production and release-equivalent Staging use PostgreSQL, not SQLite.
- Migration execution is separated from API replica startup.
- Readiness checks the expected Alembic revision in staging/production.
- PostgreSQL integration runs in CI.
- Container smoke tests run migrations, start the stack and query liveness/readiness/capabilities.
- PostgreSQL service images used by CI/local stack are pinned to an immutable image digest.
- Staging/Production configuration must not use placeholder database credentials.

Production infrastructure must additionally provide TLS, least-privilege database roles, connection limits, PITR/backups and a documented restore drill.

## 5. CI/CD and software-supply-chain gates

A candidate release is blocked when any required check fails. The implemented gate set includes:

- Python compile and API tests;
- Hugo/data/integrity validation;
- synthetic search evaluation with explicit non-production disclaimer;
- OpenAPI contract generation and pinned digest verification;
- PostgreSQL migration and Arabic FTS integration verification;
- SQLite compatibility/schema-drift verification for local/test compatibility only, not Staging evidence;
- Docker/Compose build and hardened-stack smoke test;
- working-tree and reachable-history secret scanning;
- immutable SHA pinning for active GitHub Actions;
- hashed runtime dependency graph generation;
- a reviewed SHA-256 pin that fails CI when the generated runtime dependency graph drifts;
- `pip-audit --require-hashes --strict` against that generated runtime graph;
- CycloneDX runtime dependency SBOM artifact generation;
- fail-closed release-evidence generation.

The API Dockerfile uses a multi-stage build. Build tooling is explicitly versioned and kept out of the final image. Runtime dependencies are regenerated from project metadata, checked against the pinned dependency-graph digest, materialized as wheels using hash verification, and installed into the final image without an external package index. The application wheel is built separately with no dependency resolution in the final stage.

`main` still requires repository-level Branch Protection/Ruleset enforcement. As of the verified 2026-08-22 live GitHub check, GitHub reported `main` as `protected=false`; Issue #65 tracks this Critical governance blocker and PR #66 provides the fail-closed verification workflow. CI success alone does not establish branch governance or production approval.

## 6. Runtime observability

The application emits privacy-minimized structured JSON request events containing:

- request correlation ID;
- environment;
- HTTP method;
- resolved route template rather than raw user-controlled URL path;
- status code;
- request duration.

The request telemetry deliberately excludes query strings, raw URL paths, request/response bodies, cookies, authorization values and client/network identifiers. Pre-router rejections use a neutral `__unmatched__` route value. Tests assert that representative query/token/cookie/path secrets are not emitted.

External production observability remains required for:

- aggregation, retention and access control for structured logs;
- API/search latency and error-rate metrics;
- DB pool metrics;
- authentication failure/rate-limit metrics;
- distributed tracing where justified;
- alert routing and runbooks;
- independent uptime checks.

Structured application logs are therefore an implemented telemetry primitive, not a substitute for a production monitoring stack.

## 7. Privacy and auditability

Search query logging is disabled by default. When enabled, normalized queries are represented using keyed HMAC rather than stored as raw text.

Audit events sanitize sensitive metadata, but the current relational audit table is not by itself tamper-evident. Production should export security-critical events to an append-only or integrity-protected external sink.

Internal model-provider raw payloads and benchmark evidence must be handled according to their explicit evaluation purpose; they must not be promoted to editorial evidence merely because a model produced them.

## 8. Web security and outbound-network boundary

The API/admin CSP is same-origin and restrictive. Trusted-host validation is enabled, request bodies have a configured hard size ceiling, and security headers are applied to normal API/admin responses. Any edge/CDN policy must preserve or strengthen `no-store` for admin/auth/API responses; it must not replace those headers with shared-public caching.

Staging and Production configuration require HTTPS origins, explicit non-wildcard hosts, PostgreSQL and non-placeholder credentials.

External source metadata is not a general user-controlled fetch service. A constrained Ollama provider does perform outbound HTTP to a configuration-controlled local/allowlisted endpoint; it restricts host/port, forbids credentials/path/query/fragment, rejects redirects and bounds timeout/response size. This must not be generalized into arbitrary URL fetching without a fresh SSRF design covering private/link-local targets, redirects and DNS rebinding.

## 9. Hosting and release topology

Use one declared public frontend/CDN path and one declared API runtime. Avoid simultaneously treating GitHub Pages, Vercel, Netlify and ad-hoc edge workers as independent production authorities.

Recommended responsibility split:

- Static frontend/CDN: one chosen provider.
- API: container-capable managed runtime.
- Database: managed PostgreSQL.
- Edge: DNS/WAF/distributed rate limiting.
- Observability: independent monitoring/error tracking.

Staging must exercise the same routing, PostgreSQL engine family, database migration discipline, trusted-host/CORS policy, secrets delivery model, TLS semantics and rollback path intended for production. Reduced capacity is acceptable; weakened trust assumptions are not.

## 10. AI roadmap after the retrieval foundation is proven

Do not add semantic/vector retrieval merely because it is fashionable. Controlled provider adapters or benchmarks do not by themselves justify a public generated-answer feature. The expansion sequence remains:

1. Real lexical benchmark and production-like telemetry.
2. PostgreSQL/lexical candidate retrieval at scale.
3. Embedding experiment on the same benchmark.
4. Hybrid fusion (for example reciprocal-rank fusion) only when it beats the lexical baseline by predeclared metrics.
5. Reranking only when latency/cost budgets remain acceptable.
6. Grounded public answer generation only after provenance/citation evaluation exists.
7. RAG/agent capabilities only behind explicit capability flags, evaluation suites and rollback controls.

No AI-generated answer may be represented as verified merely because the retrieval layer returned sources or because an internal provider returned text.

## 11. Release acceptance gates

`PRODUCTION_READY` is forbidden until all of the following are independently evidenced:

- required CI checks green on the final release ref;
- no known Critical or High open security finding accepted as unresolved for release;
- no real secret in repository/history/release artifacts;
- separation-of-duties production configuration enabled;
- PostgreSQL migration/integration checks green;
- backup restore successfully tested;
- distributed rate limiting/WAF active;
- MFA active and verified for privileged production accounts;
- real Arabic search benchmark meets approved targets;
- preview/manual accessibility/RTL/mobile review complete;
- external observability and alerting active;
- production rollback tested;
- live DNS/TLS/headers/sitemap/robots/canonical verification complete;
- Branch Protection/Ruleset enforcement verified on `main`;
- independent security/accessibility review completed as required;
- explicit human approval to release.

## Status vocabulary

Use only these states in project reporting:

- `NOT_STARTED`
- `DESIGNED`
- `IMPLEMENTED_NOT_INTEGRATED`
- `INTEGRATED_NOT_TESTED`
- `TESTED_IN_STAGING`
- `EXTERNALLY_VERIFIED`
- `BLOCKED`
- `PRODUCTION_READY`

Repository CI can support `INTEGRATED_NOT_TESTED`; it cannot by itself establish `TESTED_IN_STAGING`, `EXTERNALLY_VERIFIED`, or `PRODUCTION_READY`.
