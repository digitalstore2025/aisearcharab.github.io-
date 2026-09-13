from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .model_router import ModelChoice, ModelRouter
from .provider_adapter import AgentExecutionAdapter, AgentExecutionRequest, AgentExecutionResult
from .team import AgentAssignment, TeamPlan
from .tool_runtime import PolicyBoundToolRuntime, ToolExecutionResult
from .tracing import JsonlTracer


_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_LEVEL = ("low", "medium", "high", "critical")


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
    """Execute TeamPlan waves concurrently while preserving phase and review ordering."""

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
        round_results: list[ToolExecutionResult] = []
        for call in result.tool_calls:
            if call.tool not in assignment.allowed_tools:
                round_results.append(ToolExecutionResult(
                    call.tool,
                    call.action,
                    "denied",
                    reason="Agent assignment does not allow this tool",
                    rule_id="agent-tool-boundary",
                ))
                continue
            if self.tool_runtime is None:
                round_results.append(ToolExecutionResult(
                    call.tool,
                    call.action,
                    "denied",
                    reason="No tool runtime is configured",
                    rule_id="tool-runtime-missing",
                ))
                continue
            round_results.append(self.tool_runtime.run(call, environment=environment))
        return tuple(round_results)

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
            tool_round += 1
            if tool_round > self.max_tool_rounds:
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="tool-round-limit-exceeded",
                    tool_results=tuple(all_tool_results),
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

            continuation = getattr(self.adapter, "continue_with_tools", None)
            if not callable(continuation):
                return self._failed_result(
                    assignment,
                    started=started,
                    model=model,
                    output="adapter-does-not-support-tool-continuation",
                    tool_results=tuple(all_tool_results),
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
        assignments = {item.agent: item for item in plan.assignments}
        wave_names = [name for wave in plan.waves for name in wave]
        unknown = sorted(set(wave_names) - set(assignments))
        if unknown:
            raise ValueError(f"Team plan waves reference unknown agents: {', '.join(unknown)}")

        results: list[AgentRuntimeResult] = []
        context: list[tuple[str, str]] = []

        if self.tracer:
            self.tracer.emit(
                "team.execution.started",
                agents=list(plan.agents),
                waves=[list(wave) for wave in plan.waves],
                complexity=complexity,
                risk=risk,
            )

        for wave_index, wave in enumerate(plan.waves):
            snapshot = tuple(context)
            wave_results: list[AgentRuntimeResult] = []
            workers = min(self.max_workers, max(1, len(wave)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                future_map = {
                    pool.submit(
                        self._run_agent,
                        assignments[name],
                        plan.task,
                        snapshot,
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
            context.extend((item.agent, item.output[:4000]) for item in wave_results if item.status == "completed")

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
