# Web Security Gates — Chapters 11–15

## Mutations / Server Actions

No web mutation path is opened in this foundation PR. The FastAPI service already owns RBAC, CSRF, optimistic locking, step-up authentication, audit records and database transactions. Adding parallel Server Actions now would duplicate those controls and create inconsistent authorization paths.

`scripts/audit_release_gates.py` therefore rejects any `use server` directive and any App Router API route other than `/api/health` until a reviewed ADR explicitly maps the new surface to authorization, CSRF, rate-limit, logging and rollback controls.

## Authentication

FastAPI remains the authentication authority. It currently provides opaque server-side sessions, HttpOnly session cookies, readable CSRF cookies, `SameSite=Strict`, login throttling, lock handling, MFA for privileged roles, and password step-up for sensitive mutations.

A Next.js BFF login proxy is intentionally **not enabled in this PR**. Proxying authentication changes the apparent network source of login attempts; production enablement must first define the trusted reverse-proxy/WAF topology so backend login throttling does not collapse all users into one source or trust spoofable forwarding headers.

## Search exposure

Search is fail-closed by default. Setting an upstream URL is insufficient: `AISEARCH_SEARCH_ENABLED=true` is also required. Before that flag is enabled in production, require edge/WAF rate limiting, request-log query redaction, upstream capacity evidence, and a rollback switch. Redirects are rejected and response bodies are bounded before parsing.

## Browser hardening

- Enforced CSP limits scripts, styles, connections and forms to the application origin and blocks objects/frames.
- `Referrer-Policy: no-referrer` prevents URL search queries from propagating via browser referrers.
- COOP/CORP, nosniff, frame denial and restrictive Permissions Policy are set globally.
- The unused Next.js image optimizer is disabled for this local-static-asset foundation.
- Global `X-Robots-Tag` plus HTML metadata and `robots.txt` keep the pre-launch surface out of indexes.

## Error handling

- Workspace rendering errors are handled by an App Router `error.tsx` boundary.
- Missing routes use `not-found.tsx`.
- Expected search transport failure is handled locally and never falls back to an external provider.
- User-facing errors do not include upstream URLs, stack traces, credentials, or raw exception messages.

## Gate to open authentication later

Before enabling a Next BFF auth surface, require at minimum:

1. documented public web origin and private/public API topology;
2. reviewed trusted-proxy source-IP chain and login-throttle behavior;
3. cookie forwarding tests preserving `HttpOnly`, `Secure`, `Path=/` and `SameSite=Strict`;
4. browser CSRF tests proving mutation requests require the readable CSRF token as a custom header;
5. MFA enrollment, verification, recovery-code and session-revocation E2E tests;
6. no credential/session/CSRF logging;
7. staging WAF/rate-limit evidence and rollback plan.
