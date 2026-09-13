# Astra Agent OS v2

A vendor-neutral control plane for production AI agents. V2 extends the V1 skill/prompt architecture with runtime policy enforcement, MCP preflight authorization, prompt-injection inspection, model/cost routing, observability, memory/RAG contracts, provenance, task-specific completion gates, red-team structures, bounded multi-agent orchestration, and an eval-first improvement loop.

## Included
- Runtime `PolicyEngine` with allow / approval / deny outcomes and default deny.
- `MCPGateway` preflight authorization.
- Prompt-injection inspection for untrusted retrieved content.
- Skill registry/router using narrow triggers.
- Bounded agent registry with coordinator, specialists, verifiers, and independent reviewer.
- Phase-aware team planner with explicit handoffs and bounded execution waves.
- Model/cost router with economy/standard/strong/critical tiers.
- Dependency-free JSONL tracing.
- Four-namespace memory reference implementation.
- Hybrid RAG scoring, dedupe, and citation-precision helper.
- Research provenance graph primitives.
- Code and research Definitions of Done.
- Red-team finding schema.
- Static eval suites plus optional live-model adapter pattern.
- Profiles for base, AI-search, multilingual AI/RAG, and OSINT research workflows.

## Quick start
```bash
cd agent-os
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/run_static_evals.py
PYTHONPATH=src python -m agent_os.cli plan "Review auth and dependencies before production release" --complexity high --risk high
PYTHONPATH=src python -m agent_os.cli team-plan "Complete the AISearch platform end-to-end" --profile aisearch-study --complexity critical --risk high
```

`team-plan` activates portfolio mode only for broad end-to-end work. Narrow tasks select only matching specialists, plus QA and an independent reviewer; high-risk work additionally mandates the security verifier.

The model names in `config/models/catalog.json` are policy tiers/placeholders by design. Map them to the models available in your deployment rather than hard-coding a vendor-specific assumption.

## AISearch.study pilot integration
This copy is embedded under `agent-os/` and runs in **shadow/control-plane mode**. It does not deploy the site, change production data, read secrets, or autonomously merge pull requests. Repository writes are restricted to feature-branch workflows by policy; landing remains an explicit approval boundary.
