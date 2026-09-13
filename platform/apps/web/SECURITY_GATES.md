# AISearchArab Web — Security Gates

These gates keep unproven production capabilities closed. A gate may be opened only by a reviewed change that includes executable tests, observability, rollback and external evidence where code alone cannot prove the control.

## Gate 1 — Mutations / Server Actions: CLOSED

No web mutation path is opened in this foundation PR. FastAPI already owns RBAC, CSRF, optimistic locking, step-up authentication, audit records and database transactions. Parallel Next.js Server Actions would duplicate those controls and create inconsistent authorization paths.

`scripts/audit_release_gates.py` rejects any `use server` directive and any App Router API route other than `/api/health` until a reviewed ADR maps the new surface to authorization, CSRF, rate limits, logging and rollback.

Acceptance before opening:
- explicit mutation inventory;
- backend authorization mapping per action;
- CSRF and replay tests;
- idempotency/concurrency behavior;
- audit-event verification;
- rollback plan.

## Gate 2 — Next.js authentication/session BFF: CLOSED

FastAPI remains the authentication authority. Current invariants include opaque server-side sessions, HttpOnly session cookies, readable CSRF cookies, `SameSite=Strict`, login throttling, lock handling, MFA for privileged roles, and password step-up for sensitive mutations.

Proxying authentication can change the apparent source IP of login attempts and can silently weaken throttling if proxy headers are trusted incorrectly. The web foundation therefore does not expose `/api/auth` or `/api/session`.

Tracked by **Issue #96**.

Acceptance before opening:
1. documented browser → edge/WAF → Next → FastAPI topology;
2. reviewed trusted-proxy/source-IP semantics;
3. cookie forwarding tests preserving `HttpOnly`, `Secure`, `Path=/` and `SameSite=Strict`;
4. browser CSRF tests using the required custom header;
5. MFA enrollment, verification, recovery-code and revocation E2E tests;
6. step-up verification on every sensitive mutation;
7. credential/session/CSRF log-redaction evidence;
8. rate-limit evidence under IPv4/IPv6/NAT/proxy scenarios;
9. rollback that removes the BFF without weakening FastAPI controls.

## Gate 3 — Search production exposure: CLOSED BY DEFAULT

Search is fail-closed. An upstream URL alone cannot activate it; `AISEARCH_SEARCH_ENABLED=true` is also required.

Code-level controls already enforce:
- server-only fixed origin;
- no user-controlled host/path;
- redirect denial;
- timeout;
- 256 KiB streamed response cap;
- runtime contract validation;
- no LLM/third-party fallback;
- query-bearing pagination prefetch disabled;
- `Referrer-Policy: no-referrer`.

Tracked by **Issue #98**.

Acceptance before production enablement:
- edge/WAF per-client and global rate limiting;
- trusted source-IP evidence;
- CDN/reverse-proxy/APM/access-log query-string redaction;
- staging load/capacity test and latency/error budget;
- alerting on volume, timeout and upstream failures;
- tested configuration-only rollback by disabling the flag.

## Gate 4 — AI / RAG / Agents / Tool Calling: CLOSED

No generated-answer or agent capability is exposed by this foundation.

Before opening:
- threat model for prompt injection and indirect prompt injection;
- explicit tool permission model and least privilege;
- retrieval corpus provenance and citation policy;
- output-grounding/evaluation suite;
- secret isolation from model context;
- SSRF/tool egress allowlists;
- per-user/tool rate and cost limits;
- audit trail for model/tool invocations;
- kill switch and provider fallback policy that does not silently change safety guarantees.

## Gate 5 — Canonical indexing / SEO launch: CLOSED

The Next.js workspace is not yet the canonical public frontend. The foundation therefore emits:
- `robots.txt` global disallow;
- metadata `noindex, nofollow`;
- `X-Robots-Tag: noindex, nofollow, noarchive`.

Before opening:
- canonical domain ownership;
- Hugo/Next migration and redirect map;
- sitemap/canonical metadata review;
- duplicate-content check;
- public content and accessibility QA;
- security/privacy review of indexable parameters.

## Gate 6 — Repository promotion / merge enforcement: EXTERNAL BLOCKER

Green CI is advisory unless GitHub itself enforces it. Repository rulesets returned no effective rules during the red-team review, while classic branch-protection state could not be read with the integration permission.

Tracked by **Issue #97**.

Required before production promotion:
- protect `main` from direct/force pushes and deletion;
- require PRs and approving/CODEOWNER review;
- dismiss stale approvals;
- require conversation resolution;
- require Platform Web, Platform API, Security Regression, governance/site/search-evidence and CodeQL checks;
- require code-scanning protection for qualifying findings;
- document any break-glass bypass and audit it.

## Browser hardening baseline

- CSP restricts script/style/connect/image/font sources to the reviewed foundation needs.
- `script-src-attr 'none'` blocks inline event-handler attributes.
- production CSP upgrades insecure requests.
- `object-src 'none'`, `frame-ancestors 'none'`, frame denial and restrictive Permissions Policy reduce injection/clickjacking surface.
- `Referrer-Policy: no-referrer` limits search-query propagation.
- COOP/CORP and nosniff are set globally.
- unused Next.js image optimization is disabled for this local-static-asset phase.
- `X-Powered-By` is disabled.

A nonce-based strict CSP is deliberately not enabled yet because Next.js nonces require dynamic rendering. Adoption requires a dedicated performance/caching ADR and E2E evidence rather than silently making all pages dynamic.

## Supply-chain baseline

- pnpm lockfile frozen in permanent CI;
- lifecycle build scripts limited by reviewed allowlist;
- Moderate-and-above dependency audit;
- patched Vitest 4.1.11 baseline;
- Dependabot coverage for web dependencies;
- GitHub Actions pinned to commit SHAs;
- checkout credentials not persisted in permanent verification workflows;
- CodeQL `security-extended` for JS/TS and Python.

## Error and failure behavior

- expected search failures fail closed and do not select another provider;
- workspace rendering errors use App Router error boundaries;
- missing routes use `not-found.tsx`;
- user-facing errors do not expose upstream URLs, stack traces, secrets or raw exceptions;
- rollback defaults to disabling the smallest affected capability first.
