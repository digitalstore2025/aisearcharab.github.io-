# Astra Agent OS v2.2 — Phase 2 execution runtime

## Scope

Phase 2 turns the v2.1 planning control plane into a bounded execution plane while preserving the existing policy and approval boundaries.

Implemented runtime layers:

1. `TeamPlanner` produces bounded waves and explicit handoffs.
2. `TeamRuntime` validates assignments, waves, handoff direction, and the final-review invariant before worker creation. It requires exactly one independent reviewer in a dedicated final wave and routes prior-wave evidence only across declared handoffs.
3. `ModelRouter` assigns policy strength and aliases: `luna` (economy), `terra` (standard), `sol` (strong), `astra` (critical). Aliases must be non-empty strings.
4. `ModelBindingResolver` maps policy aliases to deployment model IDs through `ASTRA_MODEL_<ALIAS>` environment variables. Policy aliases are not assumed to be provider model IDs.
5. `PolicyBoundToolRuntime` enforces profile tool allowlists, production-mutation boundaries, schema validation, the MCP preflight gateway, and one-time exact-scope approvals before any registered tool handler executes.
6. `ApprovalLedger` binds grants to exact action, resource, environment, and a canonical SHA-256 fingerprint of JSON-object tool arguments. Wildcards and non-object approval arguments are rejected, and grants are consumed once under a lock.
7. `RegisteredToolExecutor` publishes only explicitly registered, schema-described functions to provider adapters. Tool arguments must be JSON objects and are validated before approvals are consumed and again immediately before handler execution. Production-read capability is immutable registration metadata and is not inferred from logical tool/action names.
8. `JsonlTracer` is thread-safe and payload-minimized. Raw task text and tool arguments are not written to runtime traces. Runtime tracing is best-effort by default so an unavailable observability sink cannot retroactively turn completed agent work into failure; `strict=True` is available when trace durability is itself a required gate.
9. `OpenAIResponsesAdapter` is optional and uses stateless Responses API calls with `store=False`. Provider function calls return to the runtime, pass policy/approval gates, execute registered handlers, and are returned as `function_call_output` before the model may continue.
10. The CLI exposes no mutation handler. Its only built-in tool path is an explicit opt-in `repo.read`, confined to a configured non-sensitive workspace root and opened through no-follow directory/file descriptors. That built-in registration explicitly carries the production-read capability.
11. The default CI/runtime adapter is deterministic `dry-run`.

## Execution semantics

- Waves are sequential; agents in the same wave may execute concurrently.
- Team plans fail closed before worker creation if assignments are duplicated, waves contain duplicate or unknown agents, any assignment is unscheduled, a wave is empty, the plan does not contain exactly one independent reviewer, or the reviewer is not alone in the final wave.
- Handoffs are validated before execution. Their source and target must both exist, the source must be scheduled in an earlier wave than the target, self-handoffs and duplicate source/target routes are rejected, and artifact labels must be bounded and non-empty.
- A target agent receives bounded context only from completed prior-wave agents that have an explicit handoff to that target. Completed work is not broadcast to unrelated later agents.
- Handoff context contains bounded textual output and completed tool evidence; it is explicitly labeled untrusted prior-wave data before reaching provider input.
- `TeamPlanner` creates the final independent-review wave, and `TeamRuntime` independently enforces the same invariant for manually supplied plans.
- Verification and independent review receive stronger model policy tiers than ordinary execution.
- Runtime is fail-closed by default: any adapter failure, unsuccessful provider response, denied tool call, pending approval, malformed provider call, malformed plan, or tool-round limit stops later waves.
- Tool calls from failed, cancelled, or incomplete provider responses are discarded and never executed.
- One provider round may execute at most one tool call. The OpenAI adapter requests `parallel_tool_calls=False`, and the runtime independently rejects multi-call rounds before any handler runs. This avoids partial side effects across heterogeneous tools that do not share a transaction.
- If an adapter returns a tool call but does not expose callable tool-continuation support, the runtime blocks the agent **before** executing any structurally executable tool handler. Safe structural denials such as assignment-tool mismatch still fail without requiring continuation capability.
- Tool calls are capped by `max_tool_rounds` to prevent unbounded provider/tool loops.
- Tool output is labeled as untrusted data when returned to the model and when forwarded through an explicit handoff; it is not automatically treated as verified evidence.
- Full agent objectives and operating instructions remain in the higher-priority provider `instructions` contract and are not silently truncated.

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

Planning-only team construction does not load the policy file:

```bash
agent-os team-plan "Implement backend API" --profile aisearch-study
```

The `plan` and `execute-team` commands load policy because they perform policy-aware routing or tool execution.

Execute orchestration without provider calls:

```bash
agent-os execute-team "Implement backend API" \
  --profile aisearch-study \
  --adapter dry-run \
  --trace-jsonl /tmp/astra-runtime.jsonl
```

Execute using the optional OpenAI adapter after model bindings and provider authentication are configured:

```bash
agent-os execute-team "Inspect the repository evidence" \
  --profile aisearch-study \
  --adapter openai \
  --enable-repo-read \
  --workspace-root . \
  --trace-jsonl /tmp/astra-runtime.jsonl
```

`--enable-repo-read` is opt-in. The configured workspace root itself is rejected if it resolves within a sensitive path such as `.ssh`, `secrets`, or `credentials`. On supported POSIX platforms, the root and every requested directory component are opened through directory file descriptors with `O_NOFOLLOW`; the final file is opened with `O_NOFOLLOW`, verified with `fstat`, and read from that same descriptor. This removes the check-then-read symlink race rather than relying on a prior resolved path check. Platforms that cannot provide the required no-follow/dir-fd primitives fail closed. Sensitive paths, `.env` files, common key/certificate suffixes, non-regular files, and files larger than 256 KiB are rejected. The CLI registers no mutation-capable handler.

## Tool/MCP integration

Tool execution is deliberately explicit. Register only known handlers and supported JSON schemas with `RegisteredToolExecutor`, then wrap it in `PolicyBoundToolRuntime`. There is no dynamic import, arbitrary shell execution, or model-controlled tool registration.

The built-in schema validator supports the bounded JSON Schema subset used by Agent OS tools: object/array/string/integer/number/boolean/null types, properties, required, additionalProperties, items, enum, string-length limits, numeric limits, and descriptions. Unsupported schema keywords fail registration rather than being silently ignored.

Only definitions whose logical tool is allowed by both the active profile and the agent assignment are exposed to a provider. A returned provider function call is mapped back to the registered logical `tool` and `action`, then passes the profile boundary, production boundary, schema validation, `MCPGateway`, and approval ledger before the handler can run.

Production access is fail-closed when `production_mutations=False`. A handler is exempted from the production-mutation boundary only when its frozen `ToolDefinition` was registered with `production_read=True`. Tool/action strings alone never grant this capability: registering a side-effecting handler under `repo:repo.read`, `public_search:search.public`, or any other read-looking name remains denied unless the trusted registration explicitly marks that exact definition as a production read. The built-in CLI `repo.read` registration is explicitly marked because its implementation is root-confined and read-only. `tests:test.run` is not marked and remains denied in production when mutations are disabled.

`production_read=True` is a trusted code/configuration decision at tool-registration time; it must never be derived from model output, provider names, user arguments, or retrieved content. `ToolDefinition` is frozen so the capability cannot be mutated after registration.

Approval-gated actions return `approval_required` unless an external caller has inserted an exact, unexpired grant into `ApprovalLedger`. Approval scope includes canonical JSON-object tool arguments. For example, a grant for `pr.merge` with `{"pr_number":126,"head_sha":"abc"}` cannot authorize PR 127 or a different head SHA. Invalid or non-object arguments are rejected before a one-time approval can be consumed. The agent/model cannot self-approve.

## Trace durability

Trace construction still fails early if the configured trace directory itself cannot be created. After successful tracer construction, event writes are best-effort by default: an `OSError` is counted in `write_failures`, the exception type is exposed through `last_write_error`, and agent execution continues. This prevents an observability-disk outage from rewriting a completed business result as an agent failure.

Deployments that require trace persistence as a compliance or audit precondition must construct `JsonlTracer(..., strict=True)`. In strict mode, write failures propagate and can be enforced by the surrounding execution environment.

## Remaining environment-specific boundaries

The core runtime does not configure cloud IAM, network sandboxes, vendor-specific remote MCP transports, production secrets, billing, durable storage, or deployment credentials. Those controls must remain outside the model and be enforced by the target environment. Production deployment, database writes, IAM changes, billing, secret access, external messaging, and PR landing remain policy-controlled actions.
