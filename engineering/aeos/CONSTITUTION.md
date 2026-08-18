# AEOS Engineering Constitution

## I. Evidence over assertion
No feature, fix, deployment, investigation pipeline, or AI-assisted change is complete solely because code or content was generated. Completion requires verifiable evidence appropriate to the change.

## II. Specification before material implementation
Material work requires a problem statement, scope, non-goals, constraints, acceptance criteria, and failure conditions before broad implementation begins.

## III. Security and source integrity are continuous gates
External input, scraped material, uploaded content, model output, source metadata, and tool responses are untrusted until validated. Secrets and sensitive investigative material must never enter the public repository.

## IV. No fake green
Never delete, bypass, weaken, or skip a check merely to make CI pass. Fix the defect or record an explicit, reviewable exception.

## V. Least privilege
GitHub Actions, agents, APIs, credentials, services, and deployment tools receive only the permissions required for the task.

## VI. Small reversible changes
Prefer small, reviewable, reversible changes. Architecture, schema, deployment, and data-contract changes require a documented recovery path.

## VII. Provenance before AI confidence
Model output is not evidence. Claims, datasets, derived findings, and published investigative material require traceable source provenance and human review where policy requires it.

## VIII. Explicit uncertainty
Missing facts, contradictory requirements, unavailable credentials, weak provenance, or unclear security boundaries trigger stop/escalation rather than fabrication.

## IX. Production truth
Production readiness requires build, configuration, security, deployment, observability, runtime behavior, and rollback/recovery evidence where relevant.

## X. Human control of high-impact actions
Production deployment, destructive data changes, permission escalation, publication of sensitive material, and security-policy exceptions require explicit human approval.
