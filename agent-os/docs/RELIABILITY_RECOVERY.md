# Reliability recovery policy

## Purpose

Agent OS treats runtime reliability as a bounded control problem rather than an instruction to "retry until it works". The core recovery layer is deterministic and vendor-neutral: it classifies an observed failure state, chooses one bounded recovery action, preserves verification/provenance requirements, and escalates or abstains when safe automatic recovery is not proven.

This is a control-plane primitive, not a production-readiness claim. Real tool execution, human approval UI, cloud IAM/network enforcement, and production telemetry remain integration responsibilities.

## Research basis

The implementation is informed by four complementary lines of evidence:

1. [Self-Healing Agentic Orchestrators for Reliable Tool-Augmented Large Language Model Systems](https://consensus.app/papers/selfhealing-agentic-orchestrators-for-reliable-babu-agrawal/34646b67281f53e8ab0ad6b797afc23e/?utm_source=chatgpt) — R. Babu and Adarsh Agrawal, 2026, arXiv, 7 citations. The paper frames agent reliability as bounded runtime control with explicit failure classes, recovery budgets, verification, and observability, and reports controlled fault-injection results favoring verifier-guided recovery over retry-only/full-replanning baselines.
2. [Verified Tool Calls Improve LLM Agent Reliability Under Non-Atomic Failures](https://consensus.app/papers/verified-tool-calls-improve-llm-agent-reliability-under-mansoor-phadke/89b0d4f8583458f4827663cce73bc63b/?utm_source=chatgpt) — Isham Kalappurackal Mansoor, Abhishek Phadke, and Pratip Rana, 2026, 3 citations. It motivates postcondition verification, verify-before-retry behavior, and idempotency awareness when a tool may have changed external state before a timeout or ambiguous return.
3. [ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions](https://consensus.app/papers/reliabilitybench-evaluating-llm-agent-reliability-under-gupta/608943cdd2da5c75bf893b6ab15dc372/?utm_source=chatgpt) — Aayush Gupta, 2026, arXiv, 30 citations. It argues that single-run success is insufficient and evaluates consistency, perturbation robustness, and controlled tool/API faults such as timeouts, rate limits, partial responses, and schema drift.
4. [PROV-AGENT: Unified Provenance for Tracking AI Agent Interactions in Agentic Workflows](https://consensus.app/papers/provagent-unified-provenance-for-tracking-ai-agent-souza-gueroudji/5b969fd368015c8fbac1d8d80976a981/?utm_source=chatgpt) — Renan Souza, Amal Gueroudji, Stephen Dewitt, Daniel Rosendo, Tirthankar Ghosal, Robert B. Ross, Prasanna Balaprakash, and R. D. da Silva, 2025, IEEE eScience, pp. 467–473, 45 citations. It motivates traceable agent-centric provenance so failures and downstream effects can be analyzed reproducibly.

These papers support the direction, not a claim that Agent OS reproduces their complete systems or published benchmark results.

## Deterministic recovery map

| Failure class | Default action | Why |
| --- | --- | --- |
| timeout/rate-limit/upstream unavailable + idempotent operation | `retry` | bounded transient retry is safe only when replay safety is known |
| timeout/partial state/uncertain side effect | `verify_before_retry` | avoid duplicate irreversible or non-atomic actions |
| malformed arguments/schema | `repair_arguments` | blind retry repeats the same defect |
| stale context | `refresh_context` | re-ground before continuing |
| contradictory evidence / verifier failure | `replan` while budget remains | change trajectory rather than repeating it |
| policy denied | `escalate` or `abstain` | policy denial is never converted into automatic retry |
| unknown failure | one bounded `replan`, then escalation/abstention | prevents infinite opaque recovery loops |
| exhausted attempt/tool/time budget | `escalate` or `abstain` | finite budgets are a hard control boundary |

## Safety invariants

1. **No blind retry after an uncertain side effect.** Verify the postcondition first.
2. **No automatic retry after a policy denial.** Policy cannot be weakened by recovery logic.
3. **Budgets are finite.** `max_attempts`, `max_tool_calls`, and `max_elapsed_seconds` must be positive and are enforced fail-closed.
4. **Verification is explicit.** Recovery decisions record whether downstream verification is required.
5. **Trace fields are payload-minimized.** The policy exposes action/reason/budget metadata, not prompts, credentials, arbitrary tool payloads, or model rationale.
6. **Escalation is a valid terminal state.** A reliable agent may stop rather than fabricate success.

## Reliability metrics

The primitive intentionally records more than task success:

- task success rate;
- silent failure rate;
- duplicate action rate;
- mean attempts;
- mean tool calls.

Production evaluation should extend this with repeated-run consistency, fault intensity, latency/cost distributions, human intervention, and end-state correctness. Text similarity alone is insufficient for side-effecting workflows.

## Fault-injection regression suite

`tests/test_reliability.py` covers deterministic scenarios including:

- idempotent timeout;
- timeout with uncertain external side effect;
- partial external state;
- verified partial state;
- rate limit/non-idempotent operation;
- alternative-path replan;
- malformed arguments;
- stale context;
- verifier failure with and without remaining budget;
- policy denial;
- exhausted budget with no human gate;
- unknown failures;
- payload-minimized trace fields;
- aggregate reliability metrics.

The current suite validates policy semantics only. It does not simulate vendor networks or claim empirical equivalence with published agent benchmarks.

## Recommended next evaluation gate

Before wiring this policy into a production tool executor, add a controlled fault-injection harness that can replay the same task under:

- timeout after dispatch;
- HTTP 429 with `Retry-After`;
- partial response;
- malformed tool schema;
- stale evidence snapshot;
- contradictory source set;
- delayed external-state visibility;
- policy denial;
- irreversible-side-effect ambiguity.

For each scenario, compare at least:

1. no recovery;
2. retry-only;
3. bounded recovery policy;
4. bounded recovery + independent verifier.

Use deterministic end-state checks where possible, report confidence intervals for aggregate rates, and keep production promotion separate from synthetic benchmark success.
