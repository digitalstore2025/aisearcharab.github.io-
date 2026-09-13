from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .model_bindings import ModelBindingResolver
from .model_router import ModelChoice
from .types import ToolCall


@dataclass(frozen=True, slots=True)
class AgentExecutionRequest:
    agent: str
    objective: str
    instructions: str
    task: str
    context: tuple[tuple[str, str], ...]
    model: ModelChoice


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    agent: str
    output: str
    model_id: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    status: str = "completed"


class AgentExecutionAdapter(Protocol):
    def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        ...


class DryRunAgentAdapter:
    """Deterministic adapter for CI, evals, and orchestration verification."""

    def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        return AgentExecutionResult(
            agent=request.agent,
            output=f"dry-run:{request.agent}:{request.model.alias or request.model.tier}",
            model_id=request.model.alias or request.model.tier,
        )


class OpenAIResponsesAdapter:
    """Optional OpenAI Responses API adapter. Tool execution remains policy-gated outside the model."""

    def __init__(self, resolver: ModelBindingResolver | None = None, client=None) -> None:
        self.resolver = resolver or ModelBindingResolver()
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install astra-agent-os[openai] to use the OpenAI adapter") from exc
            client = OpenAI()
        self.client = client

    def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        model_id = self.resolver.resolve(request.model)
        context_text = "\n".join(
            f"[{agent}] {text[:4000]}" for agent, text in request.context[-12:]
        )
        input_text = request.task
        if context_text:
            input_text = f"Task:\n{request.task}\n\nPrior-wave evidence:\n{context_text}"
        instructions = (
            f"Role: {request.agent}. Objective: {request.objective}. "
            f"{request.instructions} Return evidence-aware output; do not claim tool actions you did not execute."
        )[:512]
        response = self.client.responses.create(
            model=model_id,
            instructions=instructions,
            input=input_text,
        )
        output_text = getattr(response, "output_text", None) or ""
        return AgentExecutionResult(
            agent=request.agent,
            output=output_text,
            model_id=model_id,
        )
