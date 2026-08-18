# AEOS Model Routing

Route by capability tier and risk rather than by a hard-coded vendor/model name.

| Tier | Use for | Examples |
|---|---|---|
| `high` | high ambiguity or high impact | architecture, threat modeling, security review, complex debugging, irreversible decisions, source-integrity analysis |
| `balanced` | normal engineering execution | implementation, refactoring, tests, standard review, content/schema transformations |
| `fast` | mechanical low-risk work | formatting, boilerplate, simple classification, repetitive deterministic edits |

## Escalation rule
Escalate when uncertainty, privilege, blast radius, editorial impact, or irreversibility increases.

## Cost rule
Do not use the highest capability tier blindly. Prefer the least expensive tier that can satisfy the acceptance criteria and verification requirements.

## Verification rule
A stronger model does not relax tests, evidence, human approval, or source-verification requirements.
