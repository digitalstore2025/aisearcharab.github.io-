# Implementation status — v2.2

## Implemented
- Policy Gateway: allow / approval / deny + default deny.
- MCP preflight gateway with trust labels and prompt-injection blocking.
- Skill Registry and deterministic minimal router.
- Specialized Agent Registry with 13 bounded project roles.
- Phase-aware Team Planner with portfolio mode, bounded work waves, explicit handoffs, and independent review.
- Bounded `TeamRuntime`: sequential waves, concurrent agents inside a wave, fail-closed continuation, final independent review ordering.
- Agent tool declarations intersected with active project-profile allowlists.
- Policy-bound tool/MCP runtime with explicit handler registration; no dynamic model-controlled registration.
- Provider function-call round trips with bounded tool rounds and fail-closed handling of unsuccessful provider responses.
- Exact-scope one-time Approval Ledger bound to canonical tool arguments; wildcard approvals prohibited and consumption is thread-safe.
- Production read-vs-mutation enforcement keyed by both logical tool and action.
- Model/cost tier router plus deployment policy aliases (`luna`, `terra`, `sol`, `astra`).
- Environment-based provider model binding with placeholder fail-closed behavior.
- Optional stateless OpenAI Responses API execution adapter (`store=False`) and deterministic dry-run adapter.
- CLI `execute-team` runtime wiring with default-deny tools and an explicit opt-in, workspace-confined, non-sensitive `repo.read` handler; no CLI mutation handler.
- Thread-safe, payload-minimized JSONL observability tracing for planning, agent execution, team execution, and tools.
- Memory namespaces and verified/fresh fact gate.
- RAG dedupe/hybrid scoring/citation metric primitive.
- Definition-of-Done engines for code and research.
- Research provenance/contradiction graph primitives.
- Red-team finding schema with evidence requirement.
- Independent verifier interface.
- A/B evaluation metrics and promotion/rejection rule.
- Failure clustering for eval-driven improvement.
- Artifact hash/provenance records.
- Project profiles.
- CI workflow and static/unit eval suites covering routing, runtime ordering, provider/tool round trips, model aliases, argument-bound approvals, concurrency, production boundaries, safe CLI repository access, trace safety, installed-wheel execution, and release packaging.

## Integration boundaries intentionally left external
- Actual cloud IAM/network/sandbox enforcement.
- Vendor-specific remote MCP transport/session adapters; the core provides the guarded execution contract and explicit handler registry.
- Durable database/vector store.
- Deployment-specific model IDs, quotas, and prices.
- Production OpenTelemetry/metrics backend.
- Human approval UI or service that mints scoped Approval Ledger grants.
- Provider credentials and production deployment credentials.

These are environment-specific. The core package exposes bounded runtime control points without granting the model authority to weaken policy, mint approvals, register arbitrary tools, or perform production mutations.
