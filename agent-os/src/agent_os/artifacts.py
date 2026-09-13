from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class ArtifactRecord:
    path: str
    sha256: str
    kind: str
    source_trace_id: str = ""


def record(path: str | Path, *, kind: str, source_trace_id: str = "") -> ArtifactRecord:
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return ArtifactRecord(str(p), digest, kind, source_trace_id)
