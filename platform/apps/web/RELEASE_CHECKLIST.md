# AISearchArab Web — Release Checklist

Use this checklist for every promotion of the hardened Next.js foundation. A checked item means evidence exists; it is not a declaration based on expectation.

## A. Pre-merge code gates

- [ ] PR is not marked ready while any required check is failing or pending.
- [ ] No unresolved Critical/High security finding exists in the tested code scope.
- [ ] CI proves the supported Node 24 LTS runtime and exact reviewed 24.21.0 baseline.
- [ ] `pnpm install --frozen-lockfile` succeeds.
- [ ] `pnpm audit --audit-level moderate` reports no blocking advisory.
- [ ] Runtime and full-build CycloneDX SBOMs are generated from the installed pnpm graph, JSON-validated, and retained as the `web-cyclonedx-sbom` artifact.
- [ ] Python structure/secret/boundary audit passes.
- [ ] Python design/WCAG audit passes.
- [ ] Python FastAPI contract-drift audit passes.
- [ ] Python release/security gate audit passes.
- [ ] ESLint passes with zero warnings.
- [ ] TypeScript strict typecheck passes.
- [ ] Vitest suite passes on the patched 4.1.11 baseline.
- [ ] Next.js production build passes.
- [ ] Chromium Playwright E2E passes.
- [ ] FastAPI tests and security regression tests pass.
- [ ] Database migration/rollback/re-upgrade/schema-drift checks pass.
- [ ] Branch-enforced CodeQL JavaScript/TypeScript analysis passes release policy.
- [ ] Branch-enforced CodeQL Python analysis passes release policy.
- [ ] Any fixed security issue has a regression test/audit rule.

## B. Repository governance gate

Before merge to `main`:

- [ ] Effective branch protection or repository ruleset is proven.
- [ ] Direct/force pushes to `main` are blocked except documented break-glass policy.
- [ ] Pull request review is required.
- [ ] CODEOWNER review is required for `.github/**` and `platform/**`.
- [ ] Stale approvals are dismissed after new commits.
- [ ] Required status checks include web verify, both CodeQL jobs, API, security, governance, site and search-evidence gates.
- [ ] Conversation resolution is required.
- [ ] Qualifying code-scanning alerts block merge.

Tracked by Issue #97.

## C. Production configuration gate

- [ ] Production runtime uses the supported Node 24.x line; no Node 20/EOL deployment remains.
- [ ] Public origin is the approved HTTPS canonical origin.
- [ ] Secrets come from the deployment secret manager; none are embedded in build artifacts.
- [ ] Search flag remains `false` unless Section D is fully evidenced.
- [ ] Auth/Server Actions/RAG/Agents remain disabled unless separate approved release gates exist.
- [ ] Pre-launch `noindex` remains enabled unless canonical migration is explicitly approved.
- [ ] Rollback configuration is accessible to the on-call owner.

## D. Search production-enablement gate

Required before `AISEARCH_SEARCH_ENABLED=true`:

- [ ] WAF/edge rate limiting tested per client and globally.
- [ ] Trusted source-IP/proxy chain documented.
- [ ] Query strings redacted from CDN/reverse-proxy/APM/access logs.
- [ ] Staging load test completed with documented capacity.
- [ ] Search latency/error/timeout alert thresholds configured.
- [ ] No LLM/third-party fallback exists on search failure.
- [ ] Redirect denial and 256 KiB response cap validated in staging.
- [ ] Rollback by disabling the feature flag is demonstrated without code deployment.

Tracked by Issue #98.

## E. Authentication integration gate

Required before adding a Next.js auth/session BFF:

- [ ] ADR defines web/API/WAF topology and source-IP semantics.
- [ ] Session cookies preserve HttpOnly, Secure, SameSite and Path attributes.
- [ ] CSRF custom-header flow works end-to-end.
- [ ] MFA enrollment/verification/recovery tests pass.
- [ ] Privileged roles require MFA.
- [ ] Step-up authentication protects sensitive mutations.
- [ ] Login throttling remains per-real-client and cannot be bypassed by spoofed proxy headers.
- [ ] Credentials/session/CSRF data are absent from logs and traces.
- [ ] Session revocation is tested.
- [ ] Rollback path removes the BFF without invalidating backend security controls.

Tracked by Issue #96.

## F. Deployment validation

Immediately after deployment:

- [ ] `/api/health` responds without exposing internal dependencies or secrets.
- [ ] Expected security headers are present over the public HTTPS origin.
- [ ] CSP has no unexplained production violations.
- [ ] `X-Robots-Tag` and robots metadata match launch state.
- [ ] Primary navigation works in Arabic RTL.
- [ ] Error pages do not expose stack traces/upstream URLs.
- [ ] Search remains fail-closed when disabled.
- [ ] Observability receives errors/latency metrics without raw sensitive query data.
- [ ] Previous stable release remains available for rollback.

## G. Rollback trigger

Rollback or disable the affected feature if any of these occur:

- new Critical/High vulnerability affecting the deployed stack;
- authentication/authorization bypass;
- secret/session leakage;
- uncontrolled error-rate or latency increase;
- unexplained outbound requests or redirect behavior;
- logging of sensitive search/auth material;
- database integrity risk;
- CSP/security header regression that materially changes the threat surface.

## H. Rollback procedure

1. Disable the affected feature flag first where possible.
2. Route traffic to the previous stable/public frontend if the dynamic web layer is unhealthy.
3. Revert the release commit or deployment artifact.
4. Do not run destructive database downgrade automatically.
5. Preserve logs, audit events and relevant traces.
6. Rotate affected credentials if exposure is possible.
7. Open an incident record with timeline, root cause, containment and regression-prevention action.
8. Re-enable only after the relevant release gate is re-proven.

## Release sign-off

Record in the release/PR:

- commit SHA;
- Platform Web verify and both CodeQL check/run references;
- runtime and build SBOM artifact reference;
- repository-wide security/API workflow run IDs;
- reviewer/security-owner approval;
- deployment identifier;
- feature flags enabled/disabled;
- external evidence links for WAF/log redaction/branch rules when applicable;
- rollback target.
