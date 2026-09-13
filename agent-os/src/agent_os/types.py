from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "allow"
    APPROVAL = "approval"
    DENY = "deny"


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    SENSITIVE = "sensitive"


@dataclass(slots=True)
class Action:
    name: str
    resource: str = ""
    environment: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PolicyResult:
    decision: Decision
    reason: str
    rule_id: str


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    tool: str
    action: str
    description: str
    parameters: dict[str, Any]
    strict: bool = False


@dataclass(slots=True)
class ToolCall:
    tool: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    # Fail closed: callers must explicitly designate trusted source material.
    source_trust: TrustLevel = TrustLevel.UNTRUSTED
    provider_call_id: str = ""
    provider_name: str = ""


@dataclass(slots=True)
class TraceEvent:
    trace_id: str
    event: str
    ts: float
    data: dict[str, Any] = field(default_factory=dict)
