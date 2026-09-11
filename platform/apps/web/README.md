# AISearchArab Web — Sprint 0

Next.js web foundation for the existing `platform/` modular monolith.

## Scope

This baseline intentionally contains no authentication, RAG, agent, payment, external fetch, or generated-answer UI. Those features remain behind later architecture/security gates.

## Local commands

```bash
corepack enable
pnpm install
pnpm audit:structure
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

Health endpoint: `GET /api/health`.

## Dependency policy

Direct framework dependencies are pinned. The first CI run generates the initial `pnpm-lock.yaml`; that lock must be reviewed and committed before this branch can be considered reproducible or merge-ready.
