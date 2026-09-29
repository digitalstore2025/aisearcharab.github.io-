# Astra Agent OS v2

A vendor-neutral control plane for production AI agents. V2 extends the V1 skill/prompt architecture with runtime policy enforcement, MCP preflight authorization, prompt-injection inspection, model/cost routing, observability, memory/RAG contracts, provenance, task-specific completion gates, red-team structures, bounded multi-agent orchestration, bounded recovery controls, and an eval-first improvement loop.

## Included
- Runtime `PolicyEngine` with allow / approval / deny outcomes and default deny.
- `MCPGateway` preflight authorization.
- Prompt-injection inspection for untrusted retrieved content.
- Skill registry/router using narrow triggers.
- Bounded agent registry with coordinator, specialists, verifiers, and independent reviewer.
- Phase-aware team planner with explicit handoffs and bounded execution waves.
- Deterministic runtime recovery policy for retry, verify-before-retry, argument repair, context refresh, replan, escalation, and abstention under finite budgets.
- `RecoveryExecutor` that applies the recovery policy to real tool-call functions and checks postconditions before ambiguous replay.
- Reliability metrics for success, silent failures, duplicate actions, attempts, and tool calls.
- Reproducible synthetic fault benchmark plus a live loopback Toxiproxy network-failure gate in CI.
- Dependency-free JSONL tracing plus an optional OpenTelemetry bridge using the same payload-minimization rules.
- Model/cost router with economy/standard/strong/critical tiers.
- Four-namespace memory reference implementation.
- Hybrid RAG scoring, dedupe, and citation-precision helper.
- Research provenance graph primitives.
- Code and research Definitions of Done.
- Red-team finding schema.
- Static eval suites plus optional live-model adapter pattern.
- Profiles for base, AI-search, multilingual AI/RAG, and OSINT research workflows.

See [`docs/RELIABILITY_RECOVERY.md`](docs/RELIABILITY_RECOVERY.md) for recovery semantics and [`docs/OPEN_SOURCE_FINALIZATION.md`](docs/OPEN_SOURCE_FINALIZATION.md) for the final open-source architecture, selected tools, security boundaries, and evidence layers.

## Quick start
```bash
cd agent-os
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/run_static_evals.py
PYTHONPATH=src python scripts/run_reliability_benchmark.py --out /tmp/reliability.json
PYTHONPATH=src python -m agent_os.cli plan "Review auth and dependencies before production release" --complexity high --risk high
PYTHONPATH=src python -m agent_os.cli team-plan "Complete the AISearch platform end-to-end" --profile aisearch-study --complexity critical --risk high
```

The live Toxiproxy gate is CI-oriented and requires the pinned local Toxiproxy daemon. OpenTelemetry remains optional; CI installs the exact verification dependency set from `requirements-otel.txt` with hashes.

`team-plan` activates portfolio mode only for broad end-to-end work. Narrow tasks select only matching specialists, plus QA and an independent reviewer; high-risk work additionally mandates the security verifier.

The model names in `config/models/catalog.json` are policy tiers/placeholders by design. Map them to the models available in your deployment rather than hard-coding a vendor-specific assumption.

## AISearch.study pilot integration
This copy is embedded under `agent-os/` and runs in **shadow/control-plane mode**. It does not deploy the site, change production data, read secrets, or autonomously merge pull requests. Repository writes are restricted to feature-branch workflows by policy; landing remains an explicit approval boundary.
