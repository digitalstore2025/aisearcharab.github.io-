# Astra Agent OS v2.2 — Phase 2 execution runtime

## Scope

Phase 2 turns the v2.1 planning control plane into a bounded execution plane while preserving the existing policy and approval boundaries.

Implemented runtime layers:

1. `TeamPlanner` produces bounded waves and explicit handoffs.
2. `TeamRuntime` executes one wave at a time and runs agents within a wave concurrently.
3. `ModelRouter` assigns policy strength and aliases: `luna` (economy), `terra` (standard), `sol` (strong), `astra` (critical).
4. `ModelBindingResolver` maps policy aliases to deployment model IDs through `ASTRA_MODEL_<ALIAS>` environment variables. Policy aliases are not assumed to be provider model IDs.
5. `PolicyBoundToolRuntime` enforces profile tool allowlists, production-mutation boundaries, the MCP preflight gateway, and one-time exact-scope approvals before any registered tool handler executes.
6. `ApprovalLedger` accepts only exact action/resource/environment grants; wildcard grants are rejected and grants are consumed once.
7. `JsonlTracer` is thread-safe and payload-minimized. Raw task text and tool arguments are not written to runtime traces.
8. `OpenAIResponsesAdapter` is optional and uses the Responses API. The default CI/runtime adapter is deterministic `dry-run`.

## Execution semantics

- Waves are sequential; agents in the same wave may execute concurrently.
- A wave receives evidence only from completed prior waves, preventing same-wave hidden dependencies.
- The independent reviewer remains the dedicated final wave produced by `TeamPlanner`.
- Verification and independent review receive stronger model policy tiers than ordinary execution.
- Runtime is fail-closed by default: any adapter failure, denied tool call, or pending approval stops later waves.
- Tool output is returned to the runtime caller but is not automatically treated as verified evidence.

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

## Tool/MCP integration

Tool execution is deliberately explicit. Register only known handlers with `RegisteredToolExecutor`, then wrap it in `PolicyBoundToolRuntime`. There is no dynamic import, arbitrary shell execution, or model-controlled tool registration.

Approval-gated actions return `approval_required` unless an external caller has inserted an exact, unexpired grant into `ApprovalLedger`. The agent/model cannot self-approve.

## Remaining environment-specific boundaries

The core runtime does not configure cloud IAM, network sandboxes, vendor-specific MCP transports, production secrets, billing, or deployment credentials. Those controls must remain outside the model and be enforced by the target environment. Production deployment, database writes, IAM changes, billing, secret access, external messaging, and PR landing remain policy-controlled actions.
