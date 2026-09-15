from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .model_router import ModelChoice, ModelRouter
from .provider_adapter import AgentExecutionAdapter, AgentExecutionRequest, AgentExecutionResult
from .team import AgentAssignment, TeamPlan
from .tool_runtime import PolicyBoundToolRuntime, ToolExecutionResult
from .tracing import JsonlTracer
from .types import validate_execution_environment


_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_LEVEL = ("low", "medium", "high", "critical")
_CONTEXT_ENTRY_LIMIT = 4000
_HANDOFF_ARTIFACT_LIMIT = 160


@dataclass(frozen=True, slots=True)
class AgentRuntimeResult:
    agent: str
    status: str
    output: str
    model_id: str
    tool_results: tuple[ToolExecutionResult, ...] = ()
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class TeamExecutionReport:
    completed: bool
    results: tuple[AgentRuntimeResult, ...]
    stopped_after_wave: int | None = None


class TeamRuntime:
    """Execute validated TeamPlans with explicit handoffs and an isolated final review."""

    def __init__(
        self,
        models: ModelRouter,
        adapter: AgentExecutionAdapter,
        *,
        tool_runtime: PolicyBoundToolRuntime | None = None,
        tracer: JsonlTracer | None = None,
        max_workers: int = 4,
        max_tool_rounds: int = 4,
        fail_closed: bool = True,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be >= 1")
        self.models = models
        self.adapter = adapter
        self.tool_runtime = tool_runtime
        self.tracer = tracer
        self.max_workers = max_workers
        self.max_tool_rounds = max_tool_rounds
        self.fail_closed = fail_closed

    @staticmethod
    def _raise_level(level: str, minimum: str) -> str:
        if level not in _RANK or minimum not in _RANK:
            raise ValueError("Unsupported execution level")
        return _LEVEL[max(_RANK[level], _RANK[minimum])]

    @staticmethod
    def _validate_plan(plan: TeamPlan) -> dict[str, AgentAssignment]:
        assignment_names = [item.agent for item in plan.assignments]
        if not assignment_names:
            raise ValueError("Team plan must contain at least one assignment")
        if len(assignment_names) != len(set(assignment_names)):
            raise ValueError("Team plan contains duplicate agent assignments")
        if not plan.waves:
            raise ValueError("Team plan must contain execution waves")
        if any(not wave for wave in plan.waves):
            raise ValueError("Team plan contains an empty execution wave")

        wave_names = [name for wave in plan.waves for name in wave]
        if len(wave_names) != len(set(wave_names)):
            raise ValueError("Team plan schedules an agent more than once")

        assignment_set = set(assignment_names)
        wave_set = set(wave_names)
        unknown = sorted(wave_set - assignment_set)
        if unknown:
            raise ValueError(f"Team plan waves reference unknown agents: {', '.join(unknown)}")
        missing = sorted(assignment_set - wave_set)
        if missing:
            raise ValueError(f"Team plan leaves agents unscheduled: {', '.join(missing)}")

        independent = [item.agent for item in plan.assignments if item.independent]
        if len(independent) != 1:
            raise ValueError("Team plan must contain exactly one independent reviewer")
        reviewer = independent[0]
        if tuple(plan.waves[-1]) != (reviewer,):
            raise ValueError("Independent reviewer must be the only agent in the final wave")

        wave_index = {
            name: index
            for index, wave in enumerate(plan.waves)
            for name in wave
        }
        handoff_pairs: set[tuple[str, str]] = set()
        for handoff in plan.handoffs:
            if handoff.source not in assignment_set or handoff.target not in assignment_set:
                raise ValueError("Team plan handoff references an unknown agent")
            if handoff.source == handoff.target:
                raise ValueError("Team plan handoff cannot target its source agent")
            if not isinstance(handoff.artifact, str):
                raise ValueError("Team plan handoff artifact must be text")
            artifact = handoff.artifact.strip()
            if not artifact or len(artifact) > _HANDOFF_ARTIFACT_LIMIT:
                raise ValueError("Team plan handoff artifact must be a bounded non-empty label")
            pair = (handoff.source, handoff.target)
            if pair in handoff_pairs:
                raise ValueError("Team plan contains duplicate handoff routing")
            handoff_pairs.add(pair)
            if wave_index[handoff.source] >= wave_index[handoff.target]:
                raise ValueError("Team plan handoffs must flow from an earlier wave to a later wave")

        return {item.agent: item for item in plan.assignments}

    @staticmethod
    def _context_entry(result: AgentRuntimeResult) -> str:
        """Build bounded text and completed tool evidence for an explicit handoff."""
        sections: list[str] = []
        if result.output:
            sections.append(f"Agent output:\n{result.output[:2000]}")
        for tool in result.tool_results:
            if tool.status != "completed":
                continue
            evidence = json.dumps(tool.output, ensure_ascii=False, default=str)
            sections.append(
                f"Tool evidence [{tool.tool}:{tool.action}] (untrusted data):\n{evidence[:1500]}"
            )
        if not sections:
            sections.append("Agent completed without textual or tool evidence.")
        return "\n\n".join(sections)[:_CONTEXT_ENTRY_LIMIT]

    @staticmethod
    def _context_for(
        plan: TeamPlan,
        target: str,
        completed_context: dict[str, str],
    ) -> tuple[tuple[str, str], ...]:
        entries: list[tuple[str, str]] = []
        for handoff in plan.handoffs:
            if handoff.target != target:
                continue
            source_context = completed_context.get(handoff.source)
            if source_context is None:
                continue
            entries.append((
                handoff.source,
                f"Handoff artifact [{handoff.artifact.strip()}] (untrusted prior-wave data):\n{source_context}",
            ))
        return tuple(entries)

    def _model_for(self, assignment: AgentAssignment, *, complexity: str, risk: str) -> ModelChoice:
        effective_complexity = complexity
        effective_risk = risk
        if assignment.independent:
            effective_complexity = "critical"
            effective_risk = "critical"
        elif assignment.phase == "verify":
            effective_complexity = self._raise_level(complexity, "high")
            effective_risk = self._raise_level(risk, "high")
        elif assignment.phase == "plan":
            effective_complexity = self._raise_level(complexity, "medium")
        return self.models.choose(
            complexity=effective_complexity,
            risk=effective_risk,
            requires_tools=bool(assignment.allowed_tools),
        )

    def _failed_result(
        self,
        assignment: AgentAssignment,
        *,
        started: float,
        model: ModelChoice | None,
        output: str,
        tool_results: tuple[ToolExecutionResult, ...] = (),
        status: str = "failed",
    ) -> AgentRuntimeResult:
        result = AgentRuntimeResult(
            assignment.agent,
            status,
            output,
            (model.alias or model.model) if model else "unresolved",
            tool_results,
            time.perf_counter() - started,
        )
        self._trace_agent(result)
        return result

    def _execute_tool_round(
        self,
        assignment: AgentAssignment,
        result: AgentExecutionResult,
        *,
        environment: str,
    ) -> tuple[ToolExecutionResult, ...]:
        if len(result.tool_calls) != 1:
            raise ValueError("Exactly one tool call is allowed per execution round")
        call = result.tool_calls[0]
        if call.tool not in assignment.allowed_tools:
            return (ToolExecutionResult(
                call.tool,
                call.action,
                "denied",
                reason="Agent assignment does not allow this tool",
                rule_id="agent-tool-boundary",
            ),)
        if self.tool_runtime is None:
            return (ToolExecutionResult(
                call.tool,
                call.action,
                "denied",
                reason="No tool runtime is configured",
                rule_id="tool-runtime-missing",
            ),)
        return (self.tool_runtime.run(call, environment=environment),)

    def _run_agent(
        self,
        assignment: AgentAssignment,
        task: str,
        context: tuple[tuple[str, str], ...],
        *,
        complexity: str,
        risk: str,
        environment: str,
    ) -> AgentRuntimeResult:
        started = time.perf_counter()
        model: ModelChoice | None = None
        all_tool_results: list[ToolExecutionResult] = []
        try:
            model = self._model_for(assignment, complexity=complexity, risk=risk)
            tools = self.tool_runtime.definitions_for(assignment.allowed_tools) if self.tool_runtime else ()
            request = AgentExecutionRequest(
                agent=assignment.agent,
                objective=assignment.objective,
                instructions=assignment.instructions,
                task=task,
                context=context,
                model=model,
                tools=tools,
            )
            result: AgentExecutionResult = self.adapter.execute(request)
        except Exception as exc:
            return self._failed_result(
                assignment,
                started=started,
                model=model,
                output=f"adapter-or-routing-error:{type(exc).__name__}",
            )

        if result.status != "completed":
            return self._failed_result(
                assignment,
                started=started,
                model=model,
                output=result.output or "provider-result-not-completed",
            )

        tool_round = 0
        while result.tool_calls:
            if result.status != "completed":
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output=result.output or "provider-result-not-completed",
                    tool_results=tuple(all_tool_results),
                )
            if len(result.tool_calls) != 1:
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="multiple-tool-calls-in-one-round",
                    tool_results=tuple(all_tool_results),
                    status="blocked",
                )
            tool_round += 1
            if tool_round > self.max_tool_rounds:
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="tool-round-limit-exceeded",
                    tool_results=tuple(all_tool_results),
                )

            call = result.tool_calls[0]
            continuation = getattr(self.adapter, "continue_with_tools", None)
            could_execute = call.tool in assignment.allowed_tools and self.tool_runtime is not None
            if could_execute and not callable(continuation):
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="adapter-does-not-support-tool-continuation",
                    tool_results=tuple(all_tool_results),
                    status="blocked",
                )

            round_results = self._execute_tool_round(
                assignment,
                result,
                environment=environment,
            )
            all_tool_results.extend(round_results)
            if any(item.status != "completed" for item in round_results):
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output=result.output,
                    tool_results=tuple(all_tool_results),
                    status="blocked",
                )

            if not callable(continuation):
                # Structural denials above cannot reach this point. Keep this
                # fail-closed guard in case the execution contract changes.
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="adapter-does-not-support-tool-continuation",
                    tool_results=tuple(all_tool_results),
                    status="blocked",
                )
            try:
                result = continuation(request, result, round_results)
            except Exception as exc:
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output=f"tool-continuation-error:{type(exc).__name__}",
                    tool_results=tuple(all_tool_results),
                )

        runtime_result = AgentRuntimeResult(
            assignment.agent,
            result.status,
            result.output,
            result.model_id,
            tuple(all_tool_results),
            time.perf_counter() - started,
        )
        self._trace_agent(runtime_result)
        return runtime_result

    def _trace_agent(self, result: AgentRuntimeResult) -> None:
        if self.tracer:
            self.tracer.emit(
                "agent.execution.completed",
                agent=result.agent,
                status=result.status,
                model=result.model_id,
                tool_calls=len(result.tool_results),
                duration_s=result.duration_s,
            )

    def run(
        self,
        plan: TeamPlan,
        *,
        complexity: str = "medium",
        risk: str = "medium",
        environment: str = "development",
    ) -> TeamExecutionReport:
        environment = validate_execution_environment(environment)
        assignments = self._validate_plan(plan)
        results: list[AgentRuntimeResult] = []
        completed_context: dict[str, str] = {}

        if self.tracer:
            self.tracer.emit(
                "team.execution.started",
                agents=list(plan.agents),
                waves=[list(wave) for wave in plan.waves],
                complexity=complexity,
                risk=risk,
            )

        for wave_index, wave in enumerate(plan.waves):
            wave_results: list[AgentRuntimeResult] = []
            workers = min(self.max_workers, len(wave))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                future_map = {
                    pool.submit(
                        self._run_agent,
                        assignments[name],
                        plan.task,
                        self._context_for(plan, name, completed_context),
                        complexity=complexity,
                        risk=risk,
                        environment=environment,
                    ): name
                    for name in wave
                }
                for future in as_completed(future_map):
                    name = future_map[future]
                    try:
                        wave_results.append(future.result())
                    except Exception as exc:
                        failed = AgentRuntimeResult(
                            name,
                            "failed",
                            f"worker-error:{type(exc).__name__}",
                            "unresolved",
                        )
                        self._trace_agent(failed)
                        wave_results.append(failed)

            order = {name: index for index, name in enumerate(wave)}
            wave_results.sort(key=lambda item: order[item.agent])
            results.extend(wave_results)
            for item in wave_results:
                if item.status == "completed":
                    completed_context[item.agent] = self._context_entry(item)

            if self.fail_closed and any(item.status != "completed" for item in wave_results):
                if self.tracer:
                    self.tracer.emit(
                        "team.execution.completed",
                        status="blocked",
                        agents=[item.agent for item in results],
                        tool_calls=sum(len(item.tool_results) for item in results),
                    )
                return TeamExecutionReport(False, tuple(results), wave_index)

        if self.tracer:
            self.tracer.emit(
                "team.execution.completed",
                status="completed",
                agents=[item.agent for item in results],
                tool_calls=sum(len(item.tool_results) for item in results),
            )
        return TeamExecutionReport(True, tuple(results), None)
