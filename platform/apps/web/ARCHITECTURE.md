# AISearchArab Web Architecture — Foundation Baseline

## Role in the platform

`platform/apps/web` is the dynamic Next.js application inside the existing `platform/` modular monolith. It does **not** replace the public Hugo site during this phase.

## Rendering boundary

- App Router components are Server Components by default.
- Add `"use client"` only at the smallest interactive boundary that requires browser APIs, state, effects, or event handlers.
- A Client Component must never import from `@/server/*` or access server secrets.
- Do not pass secrets, database records, or unrestricted internal objects into Client Components. Use explicit DTOs.

## Dependency direction

```text
src/app (routes, layouts, server components)
        |
        v
src/components / src/lib
        |
        v
src/server/api (fixed server-side integration boundary)
        |
        v
FastAPI
        |
        v
PostgreSQL / ranking layer
```

`src/server` must never depend on browser/client modules.

## Network boundary

The only outbound fetch in this foundation is the fixed server-side FastAPI `/v1/search` integration. It is disabled by default, cannot derive protocol/host/path from user input, rejects redirects, applies timeout and response-size limits, and fails closed. No third-party provider, crawler, RAG or LLM fallback is enabled.

Browser-to-backend authentication integration is not introduced until the authentication, CSRF, origin and deployment topology are explicitly selected.

## Route policy

Current routes:

- `/` — public foundation page.
- `/dashboard`, `/search`, `/sources`, `/research`, `/projects` — workspace foundation routes.
- `/api/health` — the only approved Next.js API route; fixed non-sensitive payload and `Cache-Control: no-store`.

Any additional API route or Server Action requires a reviewed security/authorization decision and is rejected by the release audit until that gate is deliberately changed.

## Security invariants

1. No secrets in client bundles, source control, logs or health responses.
2. No direct database access from Client Components.
3. Authentication is not authorization; authorization checks belong close to protected data/actions.
4. Validate untrusted input on both sides of service boundaries.
5. No AI/RAG/agent capability is exposed from this web application until existing platform gates are satisfied.
6. CI failure blocks promotion.
7. Dependency graph is installed from the committed lockfile and audited for high/critical advisories.
8. Pre-launch pages remain noindex and send restrictive browser security headers.
9. Search remains disabled by default until its production WAF/rate-limit/logging gate is approved.
