# ADR-002 — Adopt AEOS Evidence-Gated Agentic Engineering

- Status: Accepted
- Date: 2026-08-18
- Scope: AI-assisted software engineering and repository automation

## Context
The repository already has a strong Static-First architecture, agent rules, secret scanning, tests, structured-data validation, Hugo build validation, and security regression checks. AI-assisted implementation still needs an explicit governance layer that defines specification discipline, stop conditions, model/tool routing, memory boundaries, and evidence requirements.

## Decision
Adopt AEOS (Evidence-Driven Agentic Engineering) as an additive governance layer. Existing `AGENTS.md`, security policy, Executive Blueprint, and CI remain authoritative project controls. AEOS must reference and reinforce them rather than duplicate or weaken them.

The mandatory execution pattern is:

Discovery → Spec → Clarify → Architecture → Risk → Tasks → Implement → Verify → Evidence → Adversarial Review → Release → Observe.

## Consequences

### Positive
- fewer unverified completion claims;
- explicit stop conditions for ambiguity and high-impact operations;
- stronger prompt-injection and source-integrity posture;
- model/tool usage can be optimized by risk and cost;
- engineering decisions become more reproducible and auditable.

### Costs
- material changes require more explicit acceptance criteria and evidence;
- agents may stop rather than improvise when critical context is unavailable;
- governance files require maintenance when architecture or CI changes.

## Non-decision
This ADR does not authorize autonomous production deployment, autonomous publication, or storage of sensitive investigative material in the public repository.
