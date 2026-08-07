## Purpose

Describe the problem, the intended invariant, and why this change is required. Do not mark a capability as implemented unless it is integrated and tested.

## Risk classification

- [ ] Editorial integrity / publication workflow
- [ ] Authentication / authorization / sessions
- [ ] Database / migration
- [ ] Search / ranking / indexing
- [ ] Privacy / logging / analytics
- [ ] CI/CD / supply chain
- [ ] Public UI / accessibility / SEO
- [ ] Documentation only

## Required verification

- [ ] Unit/integration tests cover positive and negative paths.
- [ ] Relevant PostgreSQL integration checks pass.
- [ ] Migration upgrade/check passes when schema changes are present.
- [ ] Container smoke test passes when runtime code changes.
- [ ] Hugo/data/integrity checks pass when public output changes.
- [ ] No real secret, credential, personal token, or unsafe fixture was added.
- [ ] Logs and audit metadata do not expose secrets or raw passwords.
- [ ] RBAC/CSRF/session controls were considered for admin changes.
- [ ] Concurrency and stale-write behavior were considered for state transitions.
- [ ] Search changes are evaluated against a declared benchmark rather than anecdotes.
- [ ] Rollback/migration downgrade or forward-fix strategy is documented for risky changes.

## Production-specific gates

These boxes are evidence requirements, not declarations of intent.

- [ ] Preview/staging verification completed on HTTPS.
- [ ] Distributed rate limiting/WAF behavior verified where relevant.
- [ ] Privileged MFA/step-up verified where relevant.
- [ ] Backup/restore implications verified for data changes.
- [ ] Accessibility/RTL/mobile manual review completed for UI changes.
- [ ] Observability/alerts are sufficient to detect this change failing in production.
- [ ] Independent reviewer approved security/privacy-sensitive changes.
- [ ] Human release approval obtained.

## Capability status

Choose the strongest state that is actually supported by evidence:

- `NOT_STARTED`
- `DESIGNED`
- `IMPLEMENTED_NOT_INTEGRATED`
- `INTEGRATED_NOT_TESTED`
- `TESTED_IN_STAGING`
- `EXTERNALLY_VERIFIED`
- `BLOCKED`
- `PRODUCTION_READY`

`PRODUCTION_READY` is forbidden when any required production gate above is unresolved.
