---
name: db-migration
description: Create, change, or review a database migration and its rollout.
---

Use for schema/data migrations, not ordinary query or model work.

- Inspect the affected schema and application compatibility points.
- Prefer backward-compatible expand/contract changes for live systems.
- Identify lock duration, table rewrite, backfill, rollback, and mixed-version risks.
- Validate against a disposable/local database when available.
- Production execution requires the approval boundary in `../../policy/authority-boundaries.md`.

Read `references/rollout.md` for shared/production rollout planning.
