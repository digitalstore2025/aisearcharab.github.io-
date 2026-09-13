from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .approvals import ApprovalLedger
from .mcp_gateway import MCPGateway
from .tracing import JsonlTracer
from .types import ToolCall


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    tool: str
    action: str
    status: str
    output: Any = None
    reason: str = ""
    rule_id: str = ""
    approval_required: bool = False


ToolHandler = Callable[[dict[str, Any]], Any]


class RegisteredToolExecutor:
    """Explicit in-process MCP/tool adapter registry; no dynamic imports or arbitrary commands."""

    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], ToolHandler] = {}

    def register(self, *, tool: str, action: str, handler: ToolHandler) -> None:
        key = (tool, action)
        if key in self._handlers:
            raise ValueError(f"Handler already registered for {tool}:{action}")
        self._handlers[key] = handler

    def execute(self, call: ToolCall) -> Any:
        handler = self._handlers.get((call.tool, call.action))
        if handler is None:
            raise KeyError(f"No registered handler for {call.tool}:{call.action}")
        return handler(dict(call.arguments))


class PolicyBoundToolRuntime:
    """Authorize, approval-gate, and execute tool calls with least authority."""

    _KNOWN_PRODUCTION_READS = frozenset({"repo.read", "search.public", "test.run"})

    def __init__(
        self,
        gateway: MCPGateway,
        executor: RegisteredToolExecutor,
        *,
        approvals: ApprovalLedger | None = None,
        tracer: JsonlTracer | None = None,
        profile_allowed_tools: tuple[str, ...] = (),
        production_mutations: bool = False,
    ) -> None:
        self.gateway = gateway
        self.executor = executor
        self.approvals = approvals or ApprovalLedger()
        self.tracer = tracer
        self.profile_allowed_tools = frozenset(profile_allowed_tools)
        self.production_mutations = production_mutations

    def _emit(self, result: ToolExecutionResult, duration_s: float) -> None:
        if self.tracer:
            self.tracer.emit(
                "tool.execution",
                tool=result.tool,
                action=result.action,
                decision=result.status,
                status=result.status,
                rule_id=result.rule_id,
                duration_s=duration_s,
            )

    def run(
        self,
        call: ToolCall,
        *,
        environment: str = "development",
        retrieved_text: str | None = None,
    ) -> ToolExecutionResult:
        started = time.perf_counter()
        if call.tool not in self.profile_allowed_tools:
            result = ToolExecutionResult(
                call.tool,
                call.action,
                "denied",
                reason="Tool is outside the active profile allowlist",
                rule_id="profile-tool-boundary",
            )
            self._emit(result, time.perf_counter() - started)
            return result

        if (
            environment == "production"
            and not self.production_mutations
            and call.action not in self._KNOWN_PRODUCTION_READS
        ):
            result = ToolExecutionResult(
                call.tool,
                call.action,
                "denied",
                reason="Production mutation is disabled by the active profile",
                rule_id="profile-production-boundary",
            )
            self._emit(result, time.perf_counter() - started)
            return result

        gate = self.gateway.authorize(call, environment=environment, retrieved_text=retrieved_text)
        if gate.approval_required:
            grant = self.approvals.consume(call, environment=environment)
            if grant is None:
                result = ToolExecutionResult(
                    call.tool,
                    call.action,
                    "approval_required",
                    reason=gate.reason,
                    rule_id=gate.rule_id,
                    approval_required=True,
                )
                self._emit(result, time.perf_counter() - started)
                return result
        elif not gate.allowed:
            result = ToolExecutionResult(
                call.tool,
                call.action,
                "denied",
                reason=gate.reason,
                rule_id=gate.rule_id,
            )
            self._emit(result, time.perf_counter() - started)
            return result

        try:
            output = self.executor.execute(call)
        except Exception as exc:
            result = ToolExecutionResult(
                call.tool,
                call.action,
                "failed",
                reason=f"Tool execution failed: {type(exc).__name__}",
                rule_id=gate.rule_id,
            )
            self._emit(result, time.perf_counter() - started)
            return result

        result = ToolExecutionResult(
            call.tool,
            call.action,
            "completed",
            output=output,
            reason=gate.reason,
            rule_id=gate.rule_id,
        )
        self._emit(result, time.perf_counter() - started)
        return result
