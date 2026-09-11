# AISearchArab Web — Hardened Foundation

Next.js web foundation for the existing `platform/` modular monolith.

## Scope

This baseline includes server-rendered workspace routes and a fail-closed, explicitly gated FastAPI search integration. Authentication, RAG, agents, payments, mutations and generated answers remain behind later architecture/security gates.

## Local commands

```bash
corepack enable
corepack prepare pnpm@12.3.4 --activate
pnpm install --frozen-lockfile
pnpm audit --audit-level moderate
pnpm audit:structure
pnpm audit:design
pnpm audit:api-contract
pnpm audit:release-gates
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm e2e
```

Health endpoint: `GET /api/health`.

## Search opt-in

Search performs no upstream request unless both are present:

```text
AISEARCH_SEARCH_ENABLED=true
AISEARCH_API_BASE_URL=<reviewed origin>
```

Production enablement additionally requires the WAF/rate-limit and query-log-redaction evidence documented in `SECURITY_GATES.md`.

## Dependency policy

Framework and browser-test baselines are pinned and the complete dependency graph is committed in `pnpm-lock.yaml`. CI installs only with `--frozen-lockfile`, blocks known moderate/high/critical dependency advisories, and blocks unreviewed dependency lifecycle scripts through the pnpm build allowlist. Dependabot covers this pnpm workspace weekly.
