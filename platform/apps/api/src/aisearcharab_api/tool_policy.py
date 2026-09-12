from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_PERMISSION = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
ReplayClass = Literal[
    "pure_replay_safe",
    "read_replay_safe",
    "idempotent_side_effect",
    "non_idempotent_side_effect",
]


class ToolPolicyError(PermissionError):
    """Base exception for application-enforced tool authorization failures."""


class UnknownToolError(ToolPolicyError):
    pass


class MissingToolPermission(ToolPolicyError):
    pass


class ToolApprovalRequired(ToolPolicyError):
    pass


class ToolNetworkSourceDenied(ToolPolicyError):
    pass


class ToolIdempotencyKeyRequired(ToolPolicyError):
    pass


class InvalidToolRegistration(ValueError):
    pass


def _identifier(value: str, *, field: str, pattern: re.Pattern[str]) -> str:
    normalized = value.strip()
    if not pattern.fullmatch(normalized):
        raise InvalidToolRegistration(f"{field} contains unsupported characters or length")
    return normalized


@dataclass(frozen=True, slots=True)
class ToolCapability:
    name: str
    required_permissions: frozenset[str] = frozenset()
    replay_class: ReplayClass = "pure_replay_safe"
    requires_approval: bool = False
    allowed_research_sources: frozenset[str] = frozenset()
    idempotency_key_required: bool = False

    def __post_init__(self) -> None:
        name = _identifier(self.name, field="tool name", pattern=_TOOL_NAME)
        permissions = frozenset(
            _identifier(value, field="permission", pattern=_PERMISSION) for value in self.required_permissions
        )
        sources = frozenset(
            _identifier(value, field="research source", pattern=_TOOL_NAME) for value in self.allowed_research_sources
        )
        if self.replay_class not in {
            "pure_replay_safe",
            "read_replay_safe",
            "idempotent_side_effect",
            "non_idempotent_side_effect",
        }:
            raise InvalidToolRegistration("unsupported replay_class")
        if self.replay_class == "idempotent_side_effect" and not self.idempotency_key_required:
            raise InvalidToolRegistration("idempotent side-effect tools must require an idempotency key")
        if self.replay_class == "non_idempotent_side_effect" and not self.requires_approval:
            raise InvalidToolRegistration("non-idempotent side-effect tools must require approval")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "required_permissions", permissions)
        object.__setattr__(self, "allowed_research_sources", sources)


@dataclass(frozen=True, slots=True)
class ToolInvocationContext:
    granted_permissions: frozenset[str]
    approved: bool = False
    research_source_id: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizedToolInvocation:
    capability: ToolCapability
    research_source_id: str | None
    idempotency_key: str | None


class ToolCapabilityRegistry:
    """Server-side capability boundary for model-selected tool names.

    The model may request a registered tool, but this registry decides whether the
    current application context is authorized to invoke it. A model cannot create
    tools, add permissions, select arbitrary network sources, or bypass approval.
    """

    def __init__(self, capabilities: tuple[ToolCapability, ...] | list[ToolCapability]) -> None:
        indexed: dict[str, ToolCapability] = {}
        for capability in capabilities:
            if capability.name in indexed:
                raise InvalidToolRegistration(f"duplicate tool registration: {capability.name}")
            indexed[capability.name] = capability
        self._capabilities = indexed

    def get(self, name: str) -> ToolCapability:
        normalized = name.strip()
        capability = self._capabilities.get(normalized)
        if capability is None:
            raise UnknownToolError(f"unregistered tool: {normalized}")
        return capability

    def authorize(self, name: str, context: ToolInvocationContext) -> AuthorizedToolInvocation:
        capability = self.get(name)
        granted = frozenset(context.granted_permissions)
        missing = capability.required_permissions - granted
        if missing:
            raise MissingToolPermission(f"tool permissions missing: {', '.join(sorted(missing))}")
        if capability.requires_approval and not context.approved:
            raise ToolApprovalRequired(f"tool requires approval: {capability.name}")

        source_id = context.research_source_id.strip() if context.research_source_id is not None else None
        if source_id:
            if not capability.allowed_research_sources:
                raise ToolNetworkSourceDenied("tool has no external research capability")
            if source_id not in capability.allowed_research_sources:
                raise ToolNetworkSourceDenied("research source is not allowlisted for this tool")
        elif capability.allowed_research_sources:
            raise ToolNetworkSourceDenied("tool requires an explicit allowlisted research source")

        key = context.idempotency_key.strip() if context.idempotency_key is not None else None
        if capability.idempotency_key_required and not key:
            raise ToolIdempotencyKeyRequired(f"tool requires idempotency key: {capability.name}")
        if key is not None:
            if not key or len(key) > 128 or any(ord(character) < 33 or ord(character) > 126 for character in key):
                raise ToolIdempotencyKeyRequired("idempotency key must be 1..128 visible ASCII characters")

        return AuthorizedToolInvocation(
            capability=capability,
            research_source_id=source_id,
            idempotency_key=key,
        )
