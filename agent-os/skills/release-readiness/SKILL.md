---
name: release-readiness
description: Prepare a concrete implementation for staging or production release and assess go/no-go blockers.
---

Use after an implementation exists and release readiness is part of the requested outcome.

- Identify the change surface and release-specific failure modes.
- Run or inspect the checks relevant to that surface.
- Confirm configuration, migrations, observability, rollback, and operational ownership as applicable.
- Distinguish blockers from follow-up hardening.
- Preparing a release is allowed; executing a production deployment requires explicit approval.

Read `references/gates.md` for a fuller gate list only when needed.
