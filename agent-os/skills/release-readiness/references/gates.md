# Release gates

Apply only relevant gates:

- Correctness: affected tests/build/type checks pass.
- Security: no known critical/high exploitable regression in changed surface.
- Data: migration/backfill/rollback plan is compatible with live versions.
- Operations: logs/metrics/alerts expose expected failure modes.
- Performance: changed hot paths have acceptable evidence or bounded risk.
- Rollback: application/config/data rollback path is understood.
- Documentation: operator/user changes are documented when they affect use.
