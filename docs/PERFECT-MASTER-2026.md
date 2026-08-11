# AISearcharab.com — Perfect Master 2026

## Purpose

This document is the engineering, governance, search-quality, security and launch paper for the 2026 production-readiness line. It defines what is implemented in code, what is externally required, and which claims are forbidden until they are independently verified.

## Current release line

Branch: `phase-3-1/perfect-master-2026-08-07`

The release line is based on Phase 3 and intentionally does **not** add generated answers, RAG, embeddings, crawling or payments. The priority is to make the retrieval/editorial foundation governable, measurable and operable before increasing model complexity.

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
- CSRF double-submit validation for mutations.
- Absolute session TTL plus server-side idle timeout.
- Security-sensitive user changes revoke active sessions.
- Password hashes are versioned and transparently rehashed after successful authentication when their work profile is obsolete.

External production requirement: distributed rate limiting and bot/WAF controls remain mandatory for login/admin/search. MFA or WebAuthn/step-up authentication is required before final production approval for owner/admin/publisher accounts.

## 3. Search architecture — 2026 retrieval baseline

The public API remains retrieval-only.

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

A real Arabic benchmark must replace the tiny synthetic fixture as launch evidence. Minimum target: 100 human-reviewed queries; preferred target: 250–500 queries across MSA, dialects, mixed Arabic/English, misspellings, technical product names and navigational/informational intent.

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

- Production database: managed PostgreSQL only.
- Migration execution is separated from API replica startup.
- Readiness checks the expected Alembic revision in staging/production.
- PostgreSQL integration runs in CI.
- Container smoke tests run migrations, start the stack and query liveness/readiness/capabilities.
- PostgreSQL service images used by CI/local stack are pinned to an immutable image digest.

Production infrastructure must additionally provide TLS, least-privilege database roles, connection limits, PITR/backups and a documented restore drill.

## 5. CI/CD and software-supply-chain gates

A candidate release is blocked when any required check fails. The implemented gate set includes:

- Python compile and API tests;
- Hugo/data/integrity validation;
- synthetic search evaluation with explicit non-production disclaimer;
- OpenAPI contract generation and pinned digest verification;
- PostgreSQL migration and Arabic FTS integration verification;
- SQLite compatibility/schema-drift verification;
- Docker/Compose build and hardened-stack smoke test;
- working-tree and reachable-history secret scanning;
- immutable SHA pinning for active GitHub Actions;
- hashed runtime dependency graph generation;
- a reviewed SHA-256 pin that fails CI when the generated runtime dependency graph drifts;
- `pip-audit --require-hashes --strict` against that generated runtime graph;
- CycloneDX runtime dependency SBOM artifact generation.

The API Dockerfile uses a multi-stage build. Build tooling is explicitly versioned and kept out of the final image. Runtime dependencies are regenerated from the project metadata, checked against the pinned dependency-graph digest, materialized as wheels using hash verification, and installed into the final image without an external package index. The application wheel is built separately with no dependency resolution in the final stage.

`main` still requires repository-level branch protection/required checks and independent review for security-critical paths. CI success alone does not establish production approval.

## 6. Runtime observability

The application now emits privacy-minimized structured JSON request events containing:

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

## 8. Web security

The API/admin CSP is same-origin and restrictive. Trusted-host validation is enabled, request bodies have a configured maximum declared size, and security headers are applied to normal API/admin responses. Any edge/CDN policy must preserve or strengthen `no-store` for admin/auth/API responses; it must not replace those headers with shared-public caching.

External source URLs are currently stored, not fetched. Before any crawler/fetch feature is introduced, SSRF controls must reject private/link-local destinations, unsafe redirects and DNS-rebinding paths.

## 9. Hosting and release topology

Use one declared public frontend/CDN path and one declared API runtime. Avoid simultaneously treating GitHub Pages, Vercel, Netlify and ad-hoc edge workers as independent production authorities.

Recommended responsibility split:

- Static frontend/CDN: one chosen provider.
- API: container-capable managed runtime.
- Database: managed PostgreSQL.
- Edge: DNS/WAF/distributed rate limiting.
- Observability: independent monitoring/error tracking.

Staging must exercise the same routing, database migration discipline, trusted-host/CORS policy, secrets delivery model and rollback path intended for production.

## 10. AI roadmap after the retrieval foundation is proven

Do not add semantic/vector retrieval merely because it is fashionable. The 2026 expansion sequence is:

1. Real lexical benchmark and production-like telemetry.
2. PostgreSQL/lexical candidate retrieval at scale.
3. Embedding experiment on the same benchmark.
4. Hybrid fusion (for example reciprocal-rank fusion) only when it beats the lexical baseline by predeclared metrics.
5. Reranking only when latency/cost budgets remain acceptable.
6. Grounded answer generation only after provenance/citation evaluation exists.
7. RAG/agent capabilities only behind explicit capability flags, evaluation suites and rollback controls.

No AI-generated answer may be represented as verified merely because the retrieval layer returned sources.

## 11. Release acceptance gates

`PRODUCTION_READY` is forbidden until all of the following are independently evidenced:

- required CI checks green on the final merge base;
- no known Critical security finding;
- no real secret in repository/history/release artifacts;
- separation-of-duties production configuration enabled;
- PostgreSQL migration/integration checks green;
- backup restore successfully tested;
- distributed rate limiting/WAF active;
- MFA/step-up active for privileged production accounts;
- real Arabic search benchmark meets approved targets;
- preview/manual accessibility/RTL/mobile review complete;
- external observability and alerting active;
- production rollback tested;
- live DNS/TLS/headers/sitemap/robots/canonical verification complete;
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

The current branch has passed repository CI/integration gates but has not passed an external staging environment or independent review. It must not be called `PRODUCTION_READY` until the external and staging gates above are closed.
