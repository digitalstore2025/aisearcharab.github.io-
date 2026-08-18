# AEOS Project Spec — AISearchArab

## Problem
Arabic investigative and AI-information workflows need a reproducible, source-traceable, secure publishing and research platform rather than an opaque collection of AI-generated outputs.

## Product goal
Maintain a Static-First Arabic platform that combines investigative journalism, OSINT, verification, structured data, reusable research tooling, and responsible AI assistance while preserving source provenance and human editorial control.

## Primary architecture
Source Content + Structured Data → Validation / Fact / Link / Schema Checks → Hugo Build → Static Output → GitHub Pages / configured delivery layer.

Python automation supports collection, transformation, validation, and reporting. Dynamic services are kept outside the critical public-rendering path unless a documented use case requires them.

## Non-goals
- autonomous publication without review;
- storing sensitive human-source material in the public repository;
- treating LLM output as evidence;
- adding a production database or client-side JavaScript without a demonstrated requirement;
- bypassing terms of service, CAPTCHA, authentication, or access controls.

## Mandatory acceptance criteria for material changes
- repository identity boundaries remain intact;
- no obvious secrets or sensitive investigation data are introduced;
- relevant unit/data/schema tests pass;
- Hugo build and generated-site validation pass for public-site changes;
- performance budgets remain within repository thresholds for frontend changes;
- public schema/URL/data-contract changes are explicit and reviewed;
- security/editorial risks are documented when a new trust boundary is introduced;
- remaining limitations are stated.

## Authoritative references
- `AGENTS.md`
- `docs/EXECUTIVE_BLUEPRINT.md`
- `SECURITY.md`
- `docs/SECURITY.md`
- `.github/workflows/ci.yml`
