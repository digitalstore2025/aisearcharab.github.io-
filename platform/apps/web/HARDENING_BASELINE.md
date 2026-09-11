# AISearchArab Web — Production Hardening Baseline

Status: **Release Candidate foundation; production capabilities remain gated.**

This document defines the security and architecture baseline for `platform/apps/web`. It is intentionally conservative: absence of evidence does not count as safety, and unverified capabilities remain disabled.

## Security claim

The acceptable claim for this foundation is:

> No known Critical or High vulnerability remains within the tested code scope. Controls that depend on deployment infrastructure or administrator configuration remain explicit release blockers, and unverified capabilities remain disabled/fail-closed.

Never claim the system is universally vulnerability-free.

## In-scope components

- Next.js 16.3.4 App Router web application.
- React 19.2.8 and TypeScript strict mode.
- Node.js 24 LTS runtime; CI/local baseline 24.21.0, with the package engine restricted to the supported 24.x line.
- Server-side FastAPI search client and response contract.
- FastAPI local content-path validation contract.
- Browser security headers and pre-launch indexing controls.
- pnpm dependency graph and lifecycle-script policy.
- GitHub Actions verification, Dependabot and CodeQL configuration.
- Unit, contract, Python policy and Playwright browser tests.

## Explicitly out of scope / closed gates

The following are not production-enabled by this foundation:

- Next.js authentication or session proxy.
- Server Actions and web mutation routes.
- RAG, agents, tool calling or generated-answer UI.
- Payments.
- Crawling or arbitrary outbound fetch.
- Search exposure without deployment evidence.
- Canonical indexing/SEO launch.

Opening any of these surfaces requires a reviewed ADR, abuse model, tests, observability and rollback plan.

## Trust boundaries

```text
Untrusted browser input
        |
        v
Next.js route/search parser
        |
        v
Server-only fixed-origin search client
        |
        v
FastAPI public search contract
        |
        v
Published/indexed PostgreSQL content
```

Separate privileged boundary:

```text
Administrator browser
        |
        v
FastAPI authentication + session + CSRF + MFA + step-up
        |
        v
RBAC / audited mutations / PostgreSQL
```

The Next.js foundation must not create a parallel privileged path.

## Threat model and enforced mitigations

### Input and URL confusion

Threats: open navigation, encoded separator bypass, backslash origin confusion, control characters, query/fragment injection.

Controls:
- validate local content paths in FastAPI and TypeScript;
- reject `//`, backslashes, encoded `/` or `\\`, control characters, query strings and fragments;
- resolve against a reviewed public origin and re-check the resulting origin;
- production public origin must use HTTPS.

### SSRF / upstream manipulation

Threats: attacker-controlled protocol/host/path, redirect pivot, unsafe internal fetch.

Controls:
- API origin is server-only;
- only a plain reviewed origin is accepted;
- query input changes query parameters only;
- redirects are rejected;
- no arbitrary fallback provider exists;
- search remains disabled unless `AISEARCH_SEARCH_ENABLED=true`.

### Response/resource exhaustion

Threats: oversized upstream payloads, malformed JSON, contract bombs.

Controls:
- 4.5 second request timeout;
- 256 KiB streamed response cap with reader cancellation;
- JSON content-type requirement;
- typed runtime parsing;
- server response invariants for query, limit, offset, result count and total.

### XSS / browser injection

Controls:
- React escaping by default;
- machine rejection of `dangerouslySetInnerHTML`, `eval`, `new Function`, and `document.write`;
- CSP with same-origin policy, `object-src 'none'`, `frame-ancestors 'none'`, `script-src-attr 'none'` and production insecure-request upgrade;
- no remote image optimizer surface;
- no third-party scripts in the foundation.

Nonce-based strict CSP is intentionally deferred because Next.js nonces force dynamic rendering. Introduce it only with performance evidence and dedicated E2E coverage; do not silently trade static rendering for a stronger policy without measurement.

### Search-query privacy

Controls:
- `Referrer-Policy: no-referrer`;
- web layer does not log raw queries;
- search pagination prefetch is disabled;
- production enablement requires CDN/reverse-proxy/APM query-string redaction evidence.

### Authentication / authorization

FastAPI remains the authority. Required invariants include HttpOnly session cookies, SameSite=Strict, CSRF checks, throttling, lock handling, privileged MFA and step-up for sensitive operations.

The web release gate rejects shadow auth/session routes and Server Actions until the auth integration gate is deliberately changed in a reviewed PR.

### Runtime and supply chain

Controls:
- Node 20/EOL runtime is prohibited; web runtime is restricted to supported Node 24 LTS and CI pins 24.21.0;
- `.node-version` gives local tooling the same runtime baseline;
- `@types/node` is pinned to the Node 24 type line;
- frozen pnpm lockfile;
- direct framework/test baselines reviewed and policy checked;
- pnpm lifecycle build allowlist limited to reviewed packages;
- Moderate-and-above advisory audit in CI;
- Dependabot for web npm/pnpm dependencies;
- GitHub Actions pinned to commit SHAs;
- checkout credentials are not persisted in permanent verification workflows;
- CodeQL `security-extended` runs inside the PR-enforced Platform Web workflow for JavaScript/TypeScript and Python;
- a separate CodeQL workflow remains for scheduled/default-branch rescans after merge.

## Findings resolved by the hardening pass

| Severity | Finding | Resolution |
| --- | --- | --- |
| Critical | local-looking `'/\\host'` path could resolve cross-origin under WHATWG URL rules | dual backend/web validation + origin re-check + regression tests |
| High | web contract/security audit did not trigger on backend source changes | workflow paths include FastAPI source |
| High | search could be enabled merely by setting an upstream URL | explicit fail-closed feature flag |
| Medium | redirects followed by default | `redirect: 'error'` |
| Medium | response limit was checked after full buffering | bounded stream reader and cancellation |
| Medium | URL query could leak through browser referrer | global `no-referrer` |
| Medium | search pagination could prefetch query-bearing pages | `prefetch={false}` |
| Medium | vulnerable Vitest 3.x / mocker advisory | pinned patched Vitest 4.1.11 + regenerated lockfile |
| Medium | dependency audit ignored Moderate advisories | CI threshold raised to Moderate |
| Medium | package engine allowed Node 20 after its 2026 EOL | restricted runtime to Node 24 LTS; CI/local baseline pinned to 24.21.0 |
| Low/Medium | older GitHub Action runtimes | checkout/setup-node upgraded and SHA pinned |
| Medium | standalone CodeQL workflow was not evidenced on the PR head | CodeQL matrix moved into the already-enforced Platform Web PR workflow; scheduled/default-branch workflow retained |

## External evidence gates

Code cannot prove these controls. They remain blockers for production promotion:

1. effective `main` branch protection/ruleset and required checks;
2. code-scanning merge protection for qualifying CodeQL alerts;
3. WAF/edge rate limiting and trusted source-IP topology;
4. query-string redaction in hosting/CDN/APM/access logs;
5. production secret management and rotation evidence;
6. TLS/domain/canonical ownership;
7. staging load test and error/latency budgets;
8. alert routing and incident ownership;
9. backup/restore evidence for PostgreSQL;
10. deploy rollback evidence.

## Definition of Done

A release candidate is complete only when:

- supported Node 24 LTS runtime is proven by CI;
- frozen install succeeds;
- `pnpm audit --audit-level moderate` reports no blocking advisories;
- all Python policy audits pass;
- lint and TypeScript strict checks pass;
- all unit/contract tests pass;
- Next.js production build passes;
- Chromium E2E passes;
- FastAPI tests/migrations/schema checks pass;
- security regression workflow passes;
- PR CodeQL JavaScript/TypeScript and Python jobs complete with no merge-blocking finding;
- required GitHub branch/ruleset controls are proven;
- all production feature gates remain off unless their external acceptance evidence exists.

## Rollback principle

Rollback must be configuration-first where possible:

1. disable `AISEARCH_SEARCH_ENABLED` without a code deployment;
2. route users back to the established Hugo/public frontend if the dynamic web app is unhealthy;
3. revert the release commit/PR without modifying database state;
4. do not perform destructive schema rollback automatically;
5. preserve logs/audit evidence before remediation;
6. open a post-incident issue documenting trigger, impact, containment and prevention.

## Merge blockers

- Any failed required CI check.
- Any Moderate-or-higher dependency advisory without documented, time-bounded exception approved by a security owner.
- Any unresolved Critical/High code-scanning finding.
- Missing branch protection/ruleset evidence for `main`.
- Search/Auth/Mutation/AI feature enabled without its documented security gate.
- Any secret, credential or token detected in repository content.
