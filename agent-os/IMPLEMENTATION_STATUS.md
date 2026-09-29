# Implementation status — v2.1

## Implemented
- Policy Gateway: allow / approval / deny + default deny.
- MCP preflight gateway with trust labels and prompt-injection blocking.
- Skill Registry and deterministic minimal router.
- Specialized Agent Registry with 13 bounded project roles.
- Phase-aware Team Planner with portfolio mode, bounded work waves, explicit handoffs, and independent review.
- Agent tool declarations intersected with active project-profile allowlists.
- Model/cost tier router with independent-verifier tier.
- JSONL observability tracer.
- Optional OpenTelemetry trace bridge with shared payload minimization and hash-pinned CI verification dependencies.
- Memory namespaces and verified/fresh fact gate.
- RAG dedupe/hybrid scoring/citation metric primitive.
- Definition-of-Done engines for code and research.
- Research provenance/contradiction graph primitives.
- Red-team finding schema with evidence requirement.
- Independent verifier interface.
- A/B evaluation metrics and promotion/rejection rule.
- Failure clustering for eval-driven improvement.
- Deterministic bounded runtime recovery policy with retry / verify-before-retry / argument repair / context refresh / replan / escalation / abstention decisions.
- `RecoveryExecutor` applying that policy to executable operations with postcondition verification before ambiguous replay.
- Recovery budgets across attempts, tool calls and elapsed time, with fail-closed exhaustion behavior.
- Reliability metrics for success, silent failures, duplicate actions, attempts and tool calls.
- Synthetic repeated fault benchmark with revision-bound JSON evidence.
- Live CI transport-failure gate using immutable Shopify Toxiproxy 2.12.0 image digest.
- Loopback-only Toxiproxy control client to prevent arbitrary proxy/SSRF use.
- Fault-oriented regression tests for non-atomic side effects, transient failures, stale context, verifier failures, policy denials and budget exhaustion.
- Artifact hash/provenance records.
- Project profiles.
- CI workflow and static eval suites, including agent-team routing regression cases and installed-wheel `team-plan` verification.

## Integration boundaries intentionally left external
- Actual cloud IAM/network/sandbox enforcement.
- Real MCP server execution adapters.
- Durable database/vector store.
- Vendor-specific model IDs and prices.
- Production OpenTelemetry/OTLP backend and retention policy; Agent OS now exposes the standard trace bridge.
- Human approval UI / GitHub environment approval enforcement.
- Vendor-specific concurrent agent execution adapter; v2.1 produces an explicit safe execution plan and handoff graph.
- Production-provider chaos experiments; CI now proves real local transport-failure semantics but does not estimate production failure frequency.
- Repository administration controls such as branch protection/rulesets.

These remaining items are environment/administration-specific. They are deliberately not faked by application code and must remain separate evidence gates before any `PRODUCTION_READY` claim.
