# Astra Agent OS v2.2 — Phase 2 execution runtime

## Scope

Phase 2 turns the v2.1 planning control plane into a bounded execution plane while preserving the existing policy and approval boundaries.

Implemented runtime layers:

1. `TeamPlanner` produces bounded waves and explicit handoffs.
2. `TeamRuntime` executes one wave at a time and runs agents within a wave concurrently.
3. `ModelRouter` assigns policy strength and aliases: `luna` (economy), `terra` (standard), `sol` (strong), `astra` (critical).
4. `ModelBindingResolver` maps policy aliases to deployment model IDs through `ASTRA_MODEL_<ALIAS>` environment variables. Policy aliases are not assumed to be provider model IDs.
5. `PolicyBoundToolRuntime` enforces profile tool allowlists, production-mutation boundaries, the MCP preflight gateway, and one-time exact-scope approvals before any registered tool handler executes.
6. `ApprovalLedger` binds grants to exact action, resource, environment, and a canonical SHA-256 fingerprint of tool arguments. Wildcards are rejected and grants are consumed once under a lock.
7. `RegisteredToolExecutor` publishes only explicitly registered, schema-described functions to provider adapters. Models cannot register tools dynamically.
8. `JsonlTracer` is thread-safe and payload-minimized. Raw task text and tool arguments are not written to runtime traces.
9. `OpenAIResponsesAdapter` is optional and uses stateless Responses API calls with `store=False`. Provider function calls return to the runtime, pass policy/approval gates, execute registered handlers, and are returned as `function_call_output` before the model may continue.
10. The default CI/runtime adapter is deterministic `dry-run`.

## Execution semantics

- Waves are sequential; agents in the same wave may execute concurrently.
- A wave receives evidence only from completed prior waves, preventing same-wave hidden dependencies.
- The independent reviewer remains the dedicated final wave produced by `TeamPlanner`.
- Verification and independent review receive stronger model policy tiers than ordinary execution.
- Runtime is fail-closed by default: any adapter failure, denied tool call, pending approval, malformed provider call, or tool-round limit stops later waves.
- Tool calls are capped by `max_tool_rounds` to prevent unbounded provider/tool loops.
- Tool output is labeled as untrusted data when returned to the model and is not automatically treated as verified evidence.
- Full agent objectives and operating instructions are retained in the trusted agent contract; they are not silently truncated to fit provider developer-instruction limits.

## Model deployment bindings

The catalog stores vendor-neutral policy aliases. A deployment binds them explicitly, for example:

```bash
export ASTRA_MODEL_LUNA='<provider economy model id>'
export ASTRA_MODEL_TERRA='<provider standard model id>'
export ASTRA_MODEL_SOL='<provider strong model id>'
export ASTRA_MODEL_ASTRA='<provider critical model id>'
```

Provider IDs are deployment configuration. Do not commit credentials or API keys. The OpenAI SDK reads its own authentication configuration from the environment.

## CLI

Plan only:

```bash
agent-os team-plan "Implement backend API" --profile aisearch-study
```

Execute orchestration without provider calls:

```bash
agent-os execute-team "Implement backend API" \
  --profile aisearch-study \
  --adapter dry-run \
  --trace-jsonl /tmp/astra-runtime.jsonl
```

Execute using the optional OpenAI adapter after model bindings and provider authentication are configured:

```bash
agent-os execute-team "Implement backend API" \
  --profile aisearch-study \
  --adapter openai \
  --trace-jsonl /tmp/astra-runtime.jsonl
```

The CLI intentionally registers no mutation-capable tool handlers. Tool-enabled deployments instantiate the runtime programmatically and explicitly register the minimum handlers required by that environment.

## Tool/MCP integration

Tool execution is deliberately explicit. Register only known handlers and JSON schemas with `RegisteredToolExecutor`, then wrap it in `PolicyBoundToolRuntime`. There is no dynamic import, arbitrary shell execution, or model-controlled tool registration.

Only definitions whose logical tool is allowed by both the active profile and the agent assignment are exposed to a provider. A returned provider function call is mapped back to the registered logical `tool` and `action`, then passes the profile boundary, production boundary, `MCPGateway`, and approval ledger before the handler can run.

Approval-gated actions return `approval_required` unless an external caller has inserted an exact, unexpired grant into `ApprovalLedger`. Approval scope includes the canonical tool arguments. For example, a grant for `pr.merge` with `{"pr_number":126,"head_sha":"abc"}` cannot authorize PR 127 or a different head SHA. The agent/model cannot self-approve.

## Remaining environment-specific boundaries

The core runtime does not configure cloud IAM, network sandboxes, vendor-specific remote MCP transports, production secrets, billing, or deployment credentials. Those controls must remain outside the model and be enforced by the target environment. Production deployment, database writes, IAM changes, billing, secret access, external messaging, and PR landing remain policy-controlled actions.
