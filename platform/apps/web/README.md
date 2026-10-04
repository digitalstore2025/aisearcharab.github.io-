# AISearchArab Web — Hardened Foundation

Next.js web foundation for the existing `platform/` modular monolith.

## Security posture

The defensible claim for this branch is: **no known Critical/High vulnerability remains within the tested code scope; unverified production capabilities remain disabled or fail-closed.** This is not a claim of universal vulnerability-freedom.

## Scope

This baseline includes server-rendered workspace routes and a fail-closed, explicitly gated FastAPI search integration. Authentication, RAG, agents, payments, mutations and generated answers remain behind later architecture/security gates.

Operational security documents:

- `HARDENING_BASELINE.md` — threat model, trust boundaries, resolved findings, Definition of Done and external blockers.
- `SECURITY_TEST_MATRIX.md` — threat → control → regression test → evidence mapping.
- `SECURITY_GATES.md` — gates that keep Auth/Search/Mutations/AI closed until proven.
- `RELEASE_CHECKLIST.md` — pre-merge, production, deployment and rollback checklist.

## Supported runtime

Use Node.js **24 LTS**. The reviewed baseline is `24.21.0` and `.node-version` is committed for local tooling. `package.json` rejects unsupported major lines with `>=24.17.0 <25`; CI separately verifies the exact reviewed runtime.

## Local verification

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

Production enablement additionally requires the WAF/rate-limit, query-log-redaction, capacity and rollback evidence documented in `SECURITY_GATES.md` / `RELEASE_CHECKLIST.md` and tracked in Issue #98.

## Dependency and supply-chain policy

- Next.js 16.3.4, React 19.2.8, Playwright 1.63.0, Node 24 types, and patched Vitest 4.1.11 are policy checked.
- The pnpm graph is frozen in `pnpm-lock.yaml`; the pnpm 12 multi-document lock format is not manually rewritten.
- CI installs only with `--frozen-lockfile` and blocks known Moderate/High/Critical advisories.
- CI generates **runtime and full-build CycloneDX 1.5 SBOMs from the installed pnpm graph** and retains them as `web-cyclonedx-sbom` evidence.
- Unreviewed dependency lifecycle scripts are blocked through the pnpm build allowlist.
- Dependabot covers this pnpm workspace weekly.
- GitHub Actions are pinned to reviewed commit SHAs and permanent checkout does not persist credentials.
- CodeQL `security-extended` covers JavaScript/TypeScript and Python inside the branch-enforced Platform Web workflow; a separate workflow remains for scheduled/default-branch rescans.

## Promotion rule

PR green status alone is not sufficient for production. Repository protection, code-scanning merge protection, WAF/rate-limit/log-redaction, deployment secret management, observability, backup/restore and rollback are external evidence gates. Missing evidence means the related capability remains disabled.
