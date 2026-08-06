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

Production PostgreSQL uses a GIN-backed `to_tsvector('simple', ...)` index to select a bounded candidate set before application ranking. `SEARCH_CANDIDATE_LIMIT` is bounded and defaults to 300.

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

Production infrastructure must additionally provide TLS, least-privilege database roles, connection limits, PITR/backups and a documented restore drill.

## 5. CI/CD gates

A candidate release is blocked when any required check fails. The target gate set is:

- Python compile and tests;
- Hugo/data/integrity validation;
- search benchmark;
- OpenAPI contract verification;
- PostgreSQL migration verification;
- Docker/Compose build and smoke test;
- secret scanning;
- dependency/SAST/container scanning;
- accessibility/manual UI review;
- preview deployment smoke tests.

Third-party GitHub Actions should ultimately be pinned to immutable commit SHAs. Workflow tokens should use least privilege. `main` must have required checks and independent review for security-critical paths.

## 6. Runtime observability

Production approval requires:

- structured JSON logs;
- request/trace correlation IDs;
- redaction of secrets, raw passwords and sensitive query data;
- API/search latency and error-rate metrics;
- DB pool metrics;
- authentication failure/rate-limit metrics;
- alert routing and runbooks;
- independent uptime checks.

## 7. Privacy and auditability

Search query logging is disabled by default. When enabled, normalized queries are represented using keyed HMAC rather than stored as raw text.

Audit events sanitize sensitive metadata, but the current relational audit table is not by itself tamper-evident. Production should export security-critical events to an append-only or integrity-protected external sink.

## 8. Web security

The API/admin CSP is same-origin and restrictive. Any edge/CDN policy must preserve or strengthen `no-store` for admin/auth/API responses; it must not replace those headers with shared-public caching.

External source URLs are currently stored, not fetched. Before any crawler/fetch feature is introduced, SSRF controls must reject private/link-local destinations, unsafe redirects and DNS-rebinding paths.

## 9. Hosting and release topology

Use one declared public frontend/CDN path and one declared API runtime. Avoid simultaneously treating GitHub Pages, Vercel, Netlify and ad-hoc Cloudflare Workers as independent production authorities.

Recommended responsibility split:

- Static frontend/CDN: one chosen provider.
- API: container-capable managed runtime.
- Database: managed PostgreSQL.
- Edge: DNS/WAF/rate limiting.
- Observability: independent monitoring/error tracking.

## 10. AI roadmap after the retrieval foundation is proven

Do not add semantic/vector retrieval merely because it is fashionable. The 2026 expansion sequence is:

1. Real lexical benchmark and production telemetry.
2. PostgreSQL/lexical candidate retrieval at scale.
3. Embedding experiment on the same benchmark.
4. Hybrid fusion (for example reciprocal-rank fusion) only when it beats the lexical baseline by predeclared metrics.
5. Reranking only when latency/cost budgets remain acceptable.
6. Grounded answer generation only after provenance/citation evaluation exists.
7. RAG/agent capabilities only behind explicit capability flags, evaluation suites and rollback controls.

No AI-generated answer may be represented as verified merely because the retrieval layer returned sources.

## 11. Release acceptance gates

`PRODUCTION_READY` is forbidden until all of the following are independently evidenced:

- required CI checks green;
- no known Critical security finding;
- no real secret in repository/history/release artifacts;
- separation-of-duties production configuration enabled;
- PostgreSQL migration/integration checks green;
- backup restore successfully tested;
- distributed rate limiting active;
- MFA/step-up active for privileged production accounts;
- real Arabic search benchmark meets approved targets;
- preview/manual accessibility/RTL/mobile review complete;
- observability and alerting active;
- production rollback tested;
- live DNS/TLS/headers/sitemap/robots/canonical verification complete;
- human approval to release.

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

The current branch is an implementation candidate and must not be called `PRODUCTION_READY` until the external and staging gates above are closed.
