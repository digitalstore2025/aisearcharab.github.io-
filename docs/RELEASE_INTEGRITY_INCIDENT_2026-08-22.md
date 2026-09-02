# Release integrity incident — 2026-08-22

## Summary

PR #43 upgraded FastAPI from `0.139.2` to `0.141.1` and was merged to `main` even though its PR-head `Validate platform API` run `31487187109` failed.

The failing gate was `Verify pinned runtime dependency graph`:

- expected: `739b7d909b386a999c7ef43d57ce8bea2a4a3472da9ad9d663e7dc5d41b9c289`
- actual on that PR merge fixture: `ee4ade12ed76573dc7b03da8ebf439c2073b520e9d5e29524faeb8f00110568c`

Because the dependency graph gate failed, the dependency audit/SBOM, API tests, OpenAPI verification, PostgreSQL migration checks, container smoke test, and release-evidence jobs were skipped in that run. The upgrade therefore had no complete acceptance evidence when it landed.

## Immediate containment

This branch reverts only the FastAPI version line to the last accepted version, `0.139.2`. It does not weaken or bypass the dependency-drift gate.

Do not merge this remediation until the normal final-head workflows complete successfully. If the resulting dependency graph still drifts on the current base, regenerate and review the current-base runtime lock and audit evidence rather than copying a digest from an older run.

## Governance root cause

The repository's `main` branch was not protected, so a failing CI gate was advisory rather than an enforced landing prerequisite. Issue #65 and PR #66 track live branch-governance enforcement. This incident is not closed until GitHub reports `main` as protected and the fail-closed governance check passes.

## Release state

This incident does not change the external release state to a stronger state. External Staging and Production remain blocked until the evidence gates in Issue #14 are satisfied.
