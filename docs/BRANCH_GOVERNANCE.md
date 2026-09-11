# Main branch governance

## Current verified state

Live GitHub branch evidence checked on 2026-09-11 reports:

- branch: `main`
- commit: `5a55544a92cb4315b9419ff4159d768b204b5b55`
- `protected=false`
- classic protection enforcement reported as `off`
- required status-check contexts reported as empty

Therefore repository governance remains **BLOCKED / NOT VERIFIED**. Green CI, a mergeable pull request, or a bot approval does not change that conclusion.

Issue #97 is the current repository-governance tracking issue.

## Fail-closed verification

`.github/workflows/branch-governance.yml` fetches the live GitHub branch object and passes it to `scripts/verify_branch_governance.py`.

The Python verifier fails closed unless all of the following minimum evidence is present:

1. the returned branch is exactly `main`;
2. GitHub reports `protected is True`;
3. the live payload carries a valid 40-character commit SHA.

The verifier deliberately reports `production_ready=false` even after the minimum protection floor passes. Branch protection is necessary but not sufficient for Production readiness.

The check MUST NOT be weakened to accept `protected=false` merely to produce green CI.

## Required repository controls for full closure

Before Issue #97 can be considered resolved, prove the effective GitHub configuration enforces at least:

1. Pull-request-only landing to `main`.
2. Required always-on status checks.
3. Required approving human review with stale approvals dismissed after material commits.
4. CODEOWNER review for security-sensitive paths when a viable independent reviewer exists.
5. Conversation resolution before merge.
6. Up-to-date branch or merge-queue semantics so stale CI evidence cannot be reused.
7. Force-push prevention.
8. Branch deletion prevention.
9. Code-scanning merge protection for qualifying alerts.
10. No routine bypass; any break-glass path must be attributable and audited.

## Required-check design

Only checks that emit a result on every pull request should be configured as globally required checks. Path-scoped workflows must either be normalized to emit a neutral/successful decision on irrelevant changes or remain scope-specific evidence; otherwise GitHub can deadlock a PR waiting for a check that was never created.

Candidate globally required checks should be validated against the current workflow graph before enabling the repository rule. The current Next.js release-candidate work also requires Platform Web and CodeQL evidence when its paths are affected.

## Evidence hierarchy

Use this order when reporting readiness:

`source code -> CI result -> review -> merge -> deployment -> runtime verification -> production readiness`

None of these stages implies the next one.

Automated/bot review is supplementary evidence and is not equivalent to independent security closure or human approval.

## External administrator action

The available repository integration can write workflows and source files but does not expose a safe action for changing GitHub branch/ruleset administration. An authorized repository administrator must enable the effective rules on `main` and attach API/screenshot evidence to Issue #97.

Once the live configuration is correct, rerun `Verify branch governance` unchanged. The desired result is a green check caused by `protected=true`, not by relaxing the verifier.
