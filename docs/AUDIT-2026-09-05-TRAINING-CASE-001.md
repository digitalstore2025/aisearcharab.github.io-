# AISearchArab Production Readiness Audit — Training Case #001

Date: 2026-09-05  
Baseline: `main@9c2e7d0c1d19a590ab332713f2dce1fa24727593`  
Audit branch: `audit/training-case-001-2026-09-05`  
Decision: **NO-GO for Production**

## Scope

Bounded adversarial review of repository governance, CI supply chain, capability documentation, readiness evidence, and AI-search discoverability signals. This audit does not invent Staging, infrastructure, load-test, accessibility, security-review, or search-engine evidence that is not available.

## Verified findings

### Critical — main branch governance is not enforced

Live GitHub branch evidence on 2026-09-05 reports:

```text
main protected=false
required status checks enforcement=off
```

Impact: CI can be strong while still remaining advisory at the branch-governance layer. Direct-push/stale-base governance risk is not eliminated by green workflows alone.

Remediation in this branch:

- add `.github/workflows/branch-governance.yml`;
- fail closed while GitHub reports `protected=false`;
- add `docs/BRANCH_GOVERNANCE.md` with the required external configuration.

Residual risk: **Critical remains open** until Branch Protection or a Ruleset is actually enabled in GitHub. The workflow is evidence/guardrail, not a substitute for the repository setting.

### High — mutable GitHub Actions references in readiness guardian

Baseline workflow used:

```text
actions/checkout@v4
actions/setup-python@v5
```

Impact: mutable tags enlarge the CI supply-chain trust surface and are inconsistent with the immutable-SHA convention already used by the repository's stronger workflows.

Remediation in this branch:

- pin checkout to `3d3c42e5aac5ba805825da76410c181273ba90b1`;
- pin setup-python to `ece7cb06caefa5fff74198d8649806c4678c61a1`;
- set `persist-credentials: false`;
- bound checkout depth to 1 for this workflow.

Before/after on the affected workflow:

```text
mutable action references: 2 -> 0
persisted checkout credentials explicitly disabled: no -> yes
```

### High — root README contradicted implemented repository capabilities

Baseline root documentation stated that the repository had no Backend, production database implementation, dynamic administration/authentication, or generated answers. Current `platform/README.md` and merged code document a FastAPI/PostgreSQL platform, authentication/RBAC/MFA, admin/assistant surfaces, and optional grounded generated answers.

Impact: stale capability claims damage engineering governance, onboarding, audit accuracy, and external technical credibility.

Remediation in this branch:

- distinguish static public layer from dynamic `platform/` layer;
- document implemented controls without promoting them to Production-ready claims;
- explicitly list external/runtime gates that remain blocked.

### High — `IMPLEMENTATION_STATUS.md` was stale and branch-specific

Baseline file identified an old audit branch and historical `PENDING_CI` state even though multiple later platform/security features had reached `main`.

Impact: the nominal status file could mislead operators about the current code and evidence state.

Remediation in this branch:

- reset the baseline to current `main` SHA and 2026-09-05;
- separate `IMPLEMENTED_NOT_INTEGRATED`, `PENDING_CI`, `BLOCKED_EXTERNAL`, and `BLOCKED`;
- make branch protection and Production blockers explicit.

### Medium — AI Search / GEO readiness is not externally verified

Repository main already emits a permissive robots policy (`User-agent: *`, `Allow: /`) and validates robots/sitemap/canonical surfaces in the build. However:

- direct search performed during this audit did not surface a reliable AISearchArab result for the tested exact-domain/project queries;
- absence from those results is **not proof of non-indexing**;
- external Search Console/Bing indexing evidence is not present in this audit;
- PR #80 contains additional canonical author/entity and crawler-readiness work but explicitly requires human confirmation of a public author attribution before merge.

Decision: keep AI-search discoverability as **UNVERIFIED / evidence gap**, not PASS or FAIL.

## Pull request hygiene observations

Open branches include old/diverged work. In particular, PR #11 is hundreds of commits behind current `main`, while current main already contains substantially stronger CI/security machinery. PR #68 is also stale/unmergeable and has bounded slices superseded by later PRs.

No stale PR is merged by this audit. Old PRs should be closed only when their remaining unique changes are explicitly reconciled against current main.

## Before / after measurement

| Control | Baseline | Audit branch |
|---|---:|---:|
| Live `main` protected | false | false — external blocker |
| Fail-closed branch-governance workflow in branch | absent | present |
| Mutable Actions in readiness guardian | 2 | 0 |
| Root README capability contradictions identified in scope | present | corrected |
| Implementation status anchored to current baseline | no | yes |
| Production readiness | NO-GO | NO-GO |

The correct result is **not** to inflate the Production score after documentation/CI improvements. Critical external runtime/governance gates remain unresolved.

## Remaining blockers, prioritized

### Critical

1. Enable Branch Protection/Ruleset on `main` and verify `protected=true` from the live API.

### High

2. Run all applicable workflows on one final audit PR head; do not reuse CI evidence from historical SHAs.
3. Prove real HTTPS Staging with external secrets, managed PostgreSQL backup/PITR/restore, and rollback evidence.
4. Add distributed abuse/rate-limit/WAF controls appropriate to authenticated/generated-answer paths.
5. Obtain independent security and accessibility review before Production activation.

### Medium

6. Run representative Arabic retrieval/generated-answer benchmarks with human scoring and publish revision-bound evidence.
7. Verify external observability, alerting, latency/error SLOs and load behavior in Staging.
8. Resolve/close stale PRs only after unique-diff reconciliation.
9. Complete external indexing/entity evidence for SEO/GEO/AI Search; do not equate crawler permission with citations.

## Acceptance criteria for this audit PR

- repository workflows triggered by the changed files complete on one final head SHA;
- the readiness guardian continues to preserve its deliberate NO-GO seed behavior;
- mutable Action tags do not reappear in the readiness workflow;
- documentation does not claim Production readiness;
- `branch-governance` is expected to fail until GitHub protection is enabled, and must not be weakened merely to obtain a green check.
