from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .types import TraceEvent


class JsonlTracer:
    """Dependency-free append-only trace sink; production can bridge to OpenTelemetry."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_id = uuid.uuid4().hex

    def emit(self, event: str, **data: Any) -> TraceEvent:
        item = TraceEvent(self.trace_id, event, time.time(), data)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"trace_id": item.trace_id, "event": item.event, "ts": item.ts, "data": item.data}, ensure_ascii=False) + "\n")
        return item
