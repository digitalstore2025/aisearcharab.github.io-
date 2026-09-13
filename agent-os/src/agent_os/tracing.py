from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .types import TraceEvent

_SAFE_KEYS = frozenset({
    "action", "allowed_tools", "case_id", "decision", "duration_s", "model",
    "mode", "profile", "production_mutations", "rule_id", "skills", "status",
    "task_chars", "task_sha256", "tier", "tool", "tool_calls", "variant",
})
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _CONTROL_CHARS.sub("", value)[:160]
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value[:32]]
    return f"<{type(value).__name__}:redacted>"


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    redacted: list[str] = []
    for key, value in data.items():
        if key in _SAFE_KEYS:
            safe[key] = _safe_value(value)
        else:
            redacted.append(key)
    if redacted:
        safe["redacted_fields"] = sorted(redacted)
    return safe


class JsonlTracer:
    """Append-only payload-minimized trace sink; production can bridge to OpenTelemetry."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_id = uuid.uuid4().hex

    def emit(self, event: str, **data: Any) -> TraceEvent:
        item = TraceEvent(self.trace_id, event, time.time(), _sanitize(data))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"trace_id": item.trace_id, "event": item.event, "ts": item.ts, "data": item.data}, ensure_ascii=False) + "\n")
        return item
