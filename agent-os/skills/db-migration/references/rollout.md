# Migration rollout reference

For shared/live systems consider:

1. Expand: add compatible schema/indexes without breaking old code.
2. Backfill: bounded batches; observable progress; resumable/idempotent jobs.
3. Switch: deploy code that can tolerate mixed schema/application versions.
4. Contract: remove legacy fields only after readers/writers are migrated.
5. Rollback: define what can be reversed and what requires forward repair.

Check engine-specific behavior before asserting lock/rewrite characteristics.
