# AISearchArab Automation Control Plane

This layer extends the existing AEOS governance; it does not replace `AGENTS.md`, `SECURITY.md`, CI, or `docs/ADR-002-AEOS-EVIDENCE-GATED-ENGINEERING.md`.

Execution path:

`DATA -> VALIDATION -> RULE ENGINE -> ROUTER -> AI/AGENT WORKER -> QUALITY GATE -> HUMAN APPROVAL (when required) -> ACTION -> EVIDENCE LOG`

## Deterministic first
Use rules/code for status codes, duplicate URLs, missing/short titles, meta/H1/canonical/alt checks, sitemap checks, broken links, and threshold-based GSC routing.

## AI workflow
Use models for search intent, entity extraction, semantic clustering, competitor/content-gap analysis, brief generation, anchor suggestions, and GEO/AI-search analysis.

## Agentic path
Use only for open-ended diagnosis where the next investigative step depends on evidence, e.g. traffic loss, indexation anomalies, cannibalization, or unexplained ranking changes.

## Mandatory approval gates
No autonomous production deployment, publication, delete, 301, 410, or canonical change. These remain human-approved actions and must be backed by evidence.

## Quality contract
Minimum target quality: 0.90. Public/high-impact actions require evidence and review. Generation and evaluation must be performed as separate stages.