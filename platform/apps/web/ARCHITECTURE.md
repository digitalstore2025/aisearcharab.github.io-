# AISearchArab Web Architecture — Chapter 1 Baseline

## Role in the platform

`platform/apps/web` is the dynamic Next.js application inside the existing `platform/` modular monolith. It does **not** replace the public Hugo site during this phase.

## Rendering boundary

- App Router components are Server Components by default.
- Add `"use client"` only at the smallest interactive boundary that requires browser APIs, state, effects, or event handlers.
- A Client Component must never import from `@/server/*`, import `server-only`, or access server secrets.
- Server data modules must use `import 'server-only'` once the Data Access Layer is introduced.
- Do not pass secrets, database records, or unrestricted internal objects into Client Components. Use explicit DTOs.

## Planned dependency direction

```text
src/app (routes, layouts, server components)
        |
        v
src/features (domain UI/use-cases)
        |
        v
src/server/services (authorization + orchestration)
        |
        v
src/server/dal (data access; server-only)
        |
        v
PostgreSQL / approved internal API
```

Dependencies must flow downward. `src/server` must never depend on browser/client modules.

## Network boundary

Sprint 0/Chapter 1 performs no external fetch. Future outbound access requires the existing platform gates: explicit allowlist, SSRF controls, redirect/timeout/size limits, and reviewed telemetry behavior.

Browser-to-backend integration is not introduced until the authentication, CSRF, origin, and deployment topology are explicitly selected. Prefer server-side integration where practical to reduce credential and policy exposure.

## Route policy

Current routes:

- `/` — static/minimal web foundation page.
- `/api/health` — unauthenticated liveness-style endpoint with a fixed, non-sensitive payload and `Cache-Control: no-store`.

Future route groups may use `(public)`, `(auth)`, and `(dashboard)` when the corresponding features exist. Do not create placeholder protected routes that imply nonexistent authorization.

## Security invariants

1. No secrets in client bundles, source control, logs, or health responses.
2. No direct database access from Client Components.
3. Authentication is not authorization; authorization checks belong close to protected data/actions.
4. Validate untrusted input on the server even when client validation exists.
5. No AI/RAG/agent capability is exposed from this web application until the platform's existing gates are satisfied.
6. CI failure blocks promotion.
7. Dependency graph is installed from the committed lockfile in CI.

## Chapter 1 Definition of Done

- App Router root layout and page compile.
- Server-first boundary is documented and machine-checked.
- Health route exposes no internal dependency state or secrets.
- TypeScript strict mode remains enabled.
- Frozen-lock install, audit, lint, typecheck, tests, and production build pass in CI.
