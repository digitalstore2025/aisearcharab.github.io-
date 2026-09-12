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


@dataclass(slots=True)
class ToolCall:
    tool: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    source_trust: TrustLevel = TrustLevel.TRUSTED


@dataclass(slots=True)
class TraceEvent:
    trace_id: str
    event: str
    ts: float
    data: dict[str, Any] = field(default_factory=dict)
