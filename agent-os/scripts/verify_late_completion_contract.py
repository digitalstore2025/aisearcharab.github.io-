from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.reliability import FailureClass, FailureSignal, RecoveryBudget, RecoveryPolicy
from agent_os.runtime import ExternalOutcome, OperationSpec, RecoveryExecutor


def main() -> int:
    mutations: list[str] = []
    executor = RecoveryExecutor(
        RecoveryPolicy(
            RecoveryBudget(
                max_attempts=3,
                max_tool_calls=8,
                max_elapsed_seconds=0.1,
            )
        )
    )

    def operation() -> str:
        mutations.append("record-123")
        return "record-123"

    with patch("agent_os.runtime.monotonic", side_effect=[0.0, 0.0, 0.2]):
        result = executor.execute(
            OperationSpec("create-record", idempotent=False),
            operation,
            lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
        )

    evidence = {
        "contract": "late-completion-v1",
        "success": result.success,
        "safe_stop": result.safe_stop,
        "budget_exceeded": result.budget_exceeded,
        "external_outcome": result.external_outcome.value,
        "mutation_count": len(mutations),
        "actions": list(result.actions),
        "value_preserved": result.value == "record-123",
        "passed": (
            result.success
            and not result.safe_stop
            and result.budget_exceeded
            and result.external_outcome is ExternalOutcome.SUCCEEDED
            and len(mutations) == 1
            and result.actions == ()
            and result.value == "record-123"
        ),
    }
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
