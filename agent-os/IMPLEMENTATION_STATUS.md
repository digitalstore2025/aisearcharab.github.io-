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
- Memory namespaces and verified/fresh fact gate.
- RAG dedupe/hybrid scoring/citation metric primitive.
- Definition-of-Done engines for code and research.
- Research provenance/contradiction graph primitives.
- Red-team finding schema with evidence requirement.
- Independent verifier interface.
- A/B evaluation metrics and promotion/rejection rule.
- Failure clustering for eval-driven improvement.
- Deterministic bounded runtime recovery policy with retry / verify-before-retry / argument repair / context refresh / replan / escalation / abstention decisions.
- Recovery budgets across attempts, tool calls and elapsed time, with fail-closed exhaustion behavior.
- Reliability metrics for success, silent failures, duplicate actions, attempts and tool calls.
- Fault-oriented regression tests for non-atomic side effects, transient failures, stale context, verifier failures, policy denials and budget exhaustion.
- Artifact hash/provenance records.
- Project profiles.
- CI workflow and static eval suites, including agent-team routing regression cases and installed-wheel `team-plan` verification.

## Integration boundaries intentionally left external
- Actual cloud IAM/network/sandbox enforcement.
- Real MCP server execution adapters.
- Durable database/vector store.
- Vendor-specific model IDs and prices.
- Production telemetry backend.
- Human approval UI.
- Vendor-specific concurrent agent execution adapter; v2.1 produces an explicit safe execution plan and handoff graph.
- Production fault-injection adapters and real tool postcondition probes; the core recovery policy is deterministic and testable without claiming live-system validation.

These are environment-specific. The core package exposes the control points required to integrate them without weakening policy.
