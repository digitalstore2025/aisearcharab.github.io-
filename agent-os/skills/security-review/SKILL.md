---
name: security-review
description: Review a concrete code, config, dependency, auth, or deployment change for security risk.
---

Use this skill when the requested work includes a specific security review or when a concrete change affects a security boundary.

1. Establish the changed attack surface and trust boundaries.
2. Inspect only relevant code/config/dependencies first.
3. Classify findings by evidence and severity; do not invent category-filling findings.
4. Propose the smallest robust remediation and validate affected behavior when possible.
5. Apply `../../policy/authority-boundaries.md` before any high-impact action.

Read `references/checklist.md` only for the risk classes relevant to the change.
