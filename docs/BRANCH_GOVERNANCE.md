# Main branch governance

## Verified status

Checked against the live GitHub branch object on 2026-09-05: `main` reports `protected=false` at commit `9c2e7d0c1d19a590ab332713f2dce1fa24727593`.

Until GitHub itself reports `protected=true`, branch governance MUST remain **NOT VERIFIED** in release evidence.

Repository policy MUST distinguish between:

- CI passing on a commit;
- a pull request being mergeable;
- branch governance actually being enforced by GitHub.

The first two do not prove the third.

## Required GitHub configuration

Apply a branch protection rule or repository ruleset targeting `main` with the following minimum controls:

1. Require a pull request before merging.
2. Require status checks to pass before merging.
3. Require the branch to be up to date before merging so stale-base CI evidence cannot be reused.
4. Require conversation resolution before merging.
5. Block force pushes to `main`.
6. Block deletion of `main`.
7. Do not permit routine bypass of these controls. Any emergency bypass MUST be exceptional, attributable, documented and followed by full CI validation.
8. Prefer squash merges for normal pull requests to keep release provenance bounded and auditable.

## Globally required checks

Only checks that run on every pull request should be configured as global required checks. Current always-on candidates are:

- `quality` from **Validate site**;
- `policy` from **AEOS governance**;
- `branch-governance` from **Verify branch governance**.

Do NOT globally require path-scoped checks unless their workflows are first normalized to produce a check on every pull request. Otherwise unrelated pull requests can deadlock because GitHub waits for a check that was never created.

Path-scoped platform/security checks remain mandatory evidence whenever they are triggered by the change scope, including API quality, container smoke, release evidence, security regression and pytest diagnostics.

## Human review

Target state: at least one approving human review before merge, with stale approvals dismissed after material new commits.

If the repository has only one authorized human maintainer, add a second trusted reviewer before making one approval an unconditional branch rule for all maintainer-authored pull requests. Until then, do not claim `human_review_verified=true` for self-authored changes unless an independent reviewer actually approved them.

Automated review systems are supplementary evidence and do not substitute for human approval.

## Verification and release evidence

`BRANCH_GOVERNANCE_VERIFIED=true` is permitted only when all applicable evidence is current:

1. GitHub reports `main` as protected.
2. The `branch-governance` workflow passes on the current repository state.
3. Required status checks are configured without path-filter deadlocks.
4. Force-push and deletion protections are active.
5. Pull-request-only landing is enforced.
6. Any required human-review rule has a viable independent reviewer path.

Until these conditions are demonstrated, production/release documentation must keep branch governance fail-closed and MUST NOT describe the repository as fully production-governed.

## Transitional behavior

The workflow introduced with this policy intentionally fails while `main` remains unprotected. This is expected. The workflow should turn green only after the GitHub repository setting is changed; the check itself must not contain an exception that treats `protected=false` as success.
