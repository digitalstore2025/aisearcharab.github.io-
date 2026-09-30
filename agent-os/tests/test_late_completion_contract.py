import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.reliability import FailureClass, FailureSignal, RecoveryBudget, RecoveryPolicy
from agent_os.runtime import ExternalOutcome, OperationSpec, RecoveryExecutor


class _Tracer:
    def __init__(self):
        self.events = []

    def emit(self, event, **data):
        self.events.append((event, data))


class TestLateCompletionContract(unittest.TestCase):
    def executor(self, *, tracer=None):
        return RecoveryExecutor(
            RecoveryPolicy(
                RecoveryBudget(
                    max_attempts=3,
                    max_tool_calls=8,
                    max_elapsed_seconds=0.1,
                )
            ),
            tracer=tracer,
        )

    def test_success_after_elapsed_budget_is_success_over_budget(self):
        with patch("agent_os.runtime.monotonic", side_effect=[0.0, 0.0, 0.2]):
            result = self.executor().execute(
                OperationSpec("slow-read", idempotent=True),
                lambda: "late-success",
                lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
            )

        self.assertTrue(result.success)
        self.assertFalse(result.safe_stop)
        self.assertEqual(result.value, "late-success")
        self.assertEqual(result.external_outcome, ExternalOutcome.SUCCEEDED)
        self.assertTrue(result.budget_exceeded)
        self.assertEqual(result.actions, ())

    def test_non_idempotent_late_success_is_never_replayed(self):
        tracer = _Tracer()
        mutations = []

        def operation():
            mutations.append("record-123")
            return "record-123"

        with patch("agent_os.runtime.monotonic", side_effect=[0.0, 0.0, 0.2]):
            result = self.executor(tracer=tracer).execute(
                OperationSpec("create-record", idempotent=False),
                operation,
                lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
            )

        self.assertEqual(mutations, ["record-123"])
        self.assertTrue(result.success)
        self.assertEqual(result.external_outcome, ExternalOutcome.SUCCEEDED)
        self.assertEqual(result.actions, ())
        self.assertEqual(tracer.events[-1][0], "recovery.execution.completed")
        self.assertEqual(tracer.events[-1][1]["status"], "success_over_budget")
        self.assertFalse(any(event == "recovery.execution.stopped" for event, _ in tracer.events))

    def test_budget_exhaustion_before_dispatch_proves_not_applied(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            return "unexpected"

        with patch("agent_os.runtime.monotonic", side_effect=[0.0, 0.2]):
            result = self.executor().execute(
                OperationSpec("never-dispatch"),
                operation,
                lambda exc: FailureSignal(FailureClass.TIMEOUT),
            )

        self.assertEqual(calls, 0)
        self.assertFalse(result.success)
        self.assertEqual(result.external_outcome, ExternalOutcome.NOT_APPLIED)

    def test_ambiguous_timeout_without_verifier_remains_unknown(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            raise TimeoutError("response lost after commit")

        result = RecoveryExecutor(
            RecoveryPolicy(RecoveryBudget(max_attempts=3, max_tool_calls=8, max_elapsed_seconds=10))
        ).execute(
            OperationSpec("publish-item", idempotent=False),
            operation,
            lambda exc: FailureSignal(FailureClass.TIMEOUT, side_effect_uncertain=True),
        )

        self.assertEqual(calls, 1)
        self.assertFalse(result.success)
        self.assertEqual(result.external_outcome, ExternalOutcome.UNKNOWN)
        self.assertEqual(result.actions, ("verify_before_retry",))
        self.assertEqual(result.recovered_by, "verification_unavailable")


if __name__ == "__main__":
    unittest.main()
