# AEOS — Evidence-Driven Agentic Engineering for AISearchArab

Status: adopted governance layer for AI-assisted engineering in this repository.

AEOS does not replace `AGENTS.md`, `SECURITY.md`, or `docs/EXECUTIVE_BLUEPRINT.md`. It binds them into an explicit engineering loop with specification, risk analysis, verification, evidence, and stop conditions.

## Required loop

Discovery → Spec → Clarify → Architecture → Risk → Tasks → Implement → Verify → Evidence → Adversarial Review → Release → Observe.

A change may only advance when the evidence appropriate to its risk exists. Code generation, a successful edit, or an agent assertion is not completion evidence.

## Repository mapping

- Product and editorial mission: `docs/EXECUTIVE_BLUEPRINT.md`
- Agent operating rules: `AGENTS.md`
- Security requirements: `SECURITY.md` and `docs/SECURITY.md`
- Project CI evidence: `.github/workflows/ci.yml`
- AEOS constitution: `engineering/aeos/CONSTITUTION.md`
- AEOS operating policy: `engineering/aeos/SYSTEM_POLICY.md`
- Project spec: `engineering/aeos/PROJECT_SPEC.md`
- Threat model: `engineering/aeos/THREAT_MODEL.md`
- Memory policy: `engineering/aeos/MEMORY_POLICY.md`
- Model routing: `engineering/aeos/MODEL_ROUTING.md`
- Tool policy: `engineering/aeos/TOOL_POLICY.md`

## Definition of Done

A material change is complete only when:

1. scope and acceptance criteria are explicit;
2. relevant security/privacy/editorial risks are identified;
3. the smallest coherent implementation is made;
4. repository checks relevant to the change are executed;
5. CI/build/runtime evidence is inspected rather than assumed;
6. failures are fixed or explicitly escalated, never hidden;
7. remaining limitations and uncertainty are recorded;
8. high-impact production or destructive actions retain human control.
