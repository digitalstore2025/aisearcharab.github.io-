from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from .approvals import ApprovalLedger
from .mcp_gateway import MCPGateway
from .tracing import JsonlTracer
from .types import ToolCall, ToolDefinition


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
_TOOL_NAME_INVALID = re.compile(r"[^A-Za-z0-9_-]+")
_JSON_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})
_SCHEMA_KEYS = frozenset({
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "description",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
})


def _validate_schema_definition(schema: dict[str, Any], *, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"Schema at {path} must be an object")
    unknown = set(schema) - _SCHEMA_KEYS
    if unknown:
        raise ValueError(f"Unsupported schema keyword at {path}: {sorted(unknown)[0]}")
    schema_type = schema.get("type")
    if schema_type not in _JSON_TYPES:
        raise ValueError(f"Schema at {path} must define one supported JSON type")
    enum = schema.get("enum")
    if enum is not None and (not isinstance(enum, list) or not enum):
        raise ValueError(f"Schema enum at {path} must be a non-empty list")

    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"Schema properties at {path} must be an object")
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError(f"Schema required at {path} must be a string list")
        if not set(required).issubset(properties):
            raise ValueError(f"Schema required fields at {path} must exist in properties")
        additional = schema.get("additionalProperties", True)
        if not isinstance(additional, (bool, dict)):
            raise ValueError(f"Schema additionalProperties at {path} must be boolean or schema")
        for name, child in properties.items():
            if not isinstance(name, str):
                raise ValueError(f"Schema property names at {path} must be strings")
            _validate_schema_definition(child, path=f"{path}.{name}")
        if isinstance(additional, dict):
            _validate_schema_definition(additional, path=f"{path}.*")
    elif schema_type == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise ValueError(f"Array schema at {path} must define items")
        _validate_schema_definition(items, path=f"{path}[]")

    for key in ("minLength", "maxLength"):
        if key in schema and (schema_type != "string" or not isinstance(schema[key], int) or schema[key] < 0):
            raise ValueError(f"{key} at {path} is only valid as a non-negative integer for strings")
    for key in ("minimum", "maximum"):
        if key in schema and (schema_type not in {"integer", "number"} or isinstance(schema[key], bool) or not isinstance(schema[key], (int, float))):
            raise ValueError(f"{key} at {path} is only valid for numeric schemas")


def _matches_type(value: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return value is None


def _validate_value(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    schema_type = str(schema["type"])
    if not _matches_type(value, schema_type):
        raise ValueError(f"Tool arguments fail schema type at {path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"Tool arguments fail enum at {path}")

    if schema_type == "object":
        properties: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"Tool arguments are missing required field at {path}.{missing[0]}")
        additional = schema.get("additionalProperties", True)
        for name, child_value in value.items():
            child_schema = properties.get(name)
            if child_schema is not None:
                _validate_value(child_value, child_schema, path=f"{path}.{name}")
            elif additional is False:
                raise ValueError(f"Tool arguments contain an unexpected field at {path}.{name}")
            elif isinstance(additional, dict):
                _validate_value(child_value, additional, path=f"{path}.{name}")
    elif schema_type == "array":
        for index, item in enumerate(value):
            _validate_value(item, schema["items"], path=f"{path}[{index}]")
    elif schema_type == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValueError(f"Tool arguments violate minLength at {path}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValueError(f"Tool arguments violate maxLength at {path}")
    elif schema_type in {"integer", "number"}:
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"Tool arguments violate minimum at {path}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"Tool arguments violate maximum at {path}")


class RegisteredToolExecutor:
    """Explicit in-process tool registry with fail-closed argument validation."""

    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], ToolHandler] = {}
        self._definitions: dict[str, ToolDefinition] = {}
        self._definitions_by_key: dict[tuple[str, str], ToolDefinition] = {}
        self._definition_order: list[str] = []

    @staticmethod
    def _default_name(tool: str, action: str) -> str:
        name = _TOOL_NAME_INVALID.sub("_", f"{tool}__{action}").strip("_")[:64]
        if not name:
            raise ValueError("Tool definition name cannot be empty")
        return name

    def register(
        self,
        *,
        tool: str,
        action: str,
        handler: ToolHandler,
        name: str | None = None,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        strict: bool = False,
    ) -> ToolDefinition:
        key = (tool, action)
        if key in self._handlers:
            raise ValueError(f"Handler already registered for {tool}:{action}")
        provider_name = name or self._default_name(tool, action)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", provider_name):
            raise ValueError("Provider tool name must match [A-Za-z0-9_-]{1,64}")
        if provider_name in self._definitions:
            raise ValueError(f"Provider tool name already registered: {provider_name}")
        schema = parameters if parameters is not None else {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }
        _validate_schema_definition(schema)
        if schema.get("type") != "object":
            raise ValueError("Tool parameters must use a top-level object schema")
        definition = ToolDefinition(
            provider_name,
            tool,
            action,
            description or f"Execute {action} through {tool}",
            schema,
            strict,
        )
        self._handlers[key] = handler
        self._definitions[provider_name] = definition
        self._definitions_by_key[key] = definition
        self._definition_order.append(provider_name)
        return definition

    def definitions_for(self, allowed_tools: tuple[str, ...] | set[str] | frozenset[str]) -> tuple[ToolDefinition, ...]:
        allowed = set(allowed_tools)
        return tuple(
            self._definitions[name]
            for name in self._definition_order
            if self._definitions[name].tool in allowed
        )

    def execute(self, call: ToolCall) -> Any:
        key = (call.tool, call.action)
        handler = self._handlers.get(key)
        definition = self._definitions_by_key.get(key)
        if handler is None or definition is None:
            raise KeyError(f"No registered handler for {call.tool}:{call.action}")
        arguments = dict(call.arguments)
        _validate_value(arguments, definition.parameters)
        return handler(arguments)


class PolicyBoundToolRuntime:
    """Authorize, approval-gate, and execute tool calls with least authority."""

    _KNOWN_PRODUCTION_READS = frozenset({
        ("repo", "repo.read"),
        ("public_search", "search.public"),
        ("tests", "test.run"),
    })

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

    def definitions_for(self, assignment_allowed_tools: tuple[str, ...]) -> tuple[ToolDefinition, ...]:
        effective = self.profile_allowed_tools.intersection(assignment_allowed_tools)
        return self.executor.definitions_for(effective)

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
            and (call.tool, call.action) not in self._KNOWN_PRODUCTION_READS
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
