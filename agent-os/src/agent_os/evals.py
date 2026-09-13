from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(slots=True)
class EvalResult:
    passed: int
    total: int
    failures: list[str]

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_cases(cases: list[dict], evaluator: Callable[[dict], tuple[bool, str]]) -> EvalResult:
    failures: list[str] = []
    passed = 0
    for case in cases:
        ok, detail = evaluator(case)
        if ok:
            passed += 1
        else:
            failures.append(f"{case.get('id','unknown')}: {detail}")
    return EvalResult(passed, len(cases), failures)
