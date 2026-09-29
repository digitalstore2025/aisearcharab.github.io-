import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.reliability import FailureClass, FailureSignal, RecoveryBudget, RecoveryPolicy
from agent_os.runtime import OperationSpec, RecoveryExecutor


class _Tracer:
    def __init__(self):
        self.events = []

    def emit(self, event, **data):
        self.events.append((event, data))
        return None


class TestRecoveryExecutor(unittest.TestCase):
    def executor(self, *, attempts=3):
        return RecoveryExecutor(
            RecoveryPolicy(RecoveryBudget(max_attempts=attempts, max_tool_calls=8, max_elapsed_seconds=10))
        )

    def test_idempotent_transient_failure_retries_once(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("network timeout")
            return "ok"

        result = self.executor().execute(
            OperationSpec("read-source", idempotent=True),
            operation,
            lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.value, "ok")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(result.actions, ("retry",))

    def test_uncertain_side_effect_is_verified_before_any_replay(self):
        mutations = 0

        def operation():
            nonlocal mutations
            mutations += 1
            raise TimeoutError("response lost after commit")

        result = self.executor().execute(
            OperationSpec("publish-item"),
            operation,
            lambda exc: FailureSignal(FailureClass.TIMEOUT, side_effect_uncertain=True),
            verify_postcondition=lambda: mutations == 1,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.recovered_by, "postcondition_verified")
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.verification_calls, 1)
        self.assertEqual(mutations, 1)

    def test_verified_absence_can_allow_explicit_safe_replay(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("failed before commit")
            return "created"

        result = self.executor().execute(
            OperationSpec("create-item", retry_after_verified_absence=True),
            operation,
            lambda exc: FailureSignal(FailureClass.TIMEOUT, side_effect_uncertain=True),
            verify_postcondition=lambda: False,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.verification_calls, 1)

    def test_non_replayable_operation_stops_after_verified_absence(self):
        result = self.executor().execute(
            OperationSpec("irreversible-send"),
            lambda: (_ for _ in ()).throw(TimeoutError("ambiguous")),
            lambda exc: FailureSignal(FailureClass.TIMEOUT, side_effect_uncertain=True),
            verify_postcondition=lambda: False,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.safe_stop)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.recovered_by, "unsafe_replay_after_verified_absence")

    def test_stale_context_refreshes_then_retries(self):
        refreshed = False

        def operation():
            if not refreshed:
                raise RuntimeError("stale")
            return "fresh"

        def refresh():
            nonlocal refreshed
            refreshed = True

        result = self.executor().execute(
            OperationSpec("research-read", idempotent=True),
            operation,
            lambda exc: FailureSignal(FailureClass.STALE_CONTEXT, idempotent=True),
            refresh_context=refresh,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.value, "fresh")
        self.assertEqual(result.actions, ("refresh_context",))

    def test_malformed_arguments_are_repaired_before_retry(self):
        repaired = False

        def operation():
            if not repaired:
                raise ValueError("bad schema")
            return "accepted"

        def repair():
            nonlocal repaired
            repaired = True

        result = self.executor().execute(
            OperationSpec("structured-tool", idempotent=True),
            operation,
            lambda exc: FailureSignal(FailureClass.MALFORMED_ARGUMENTS, idempotent=True),
            repair_arguments=repair,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.actions, ("repair_arguments",))

    def test_contradictory_evidence_replans_then_retries(self):
        replanned = False

        def operation():
            if not replanned:
                raise RuntimeError("conflict")
            return "verified"

        def replan():
            nonlocal replanned
            replanned = True

        result = self.executor().execute(
            OperationSpec("evidence-synthesis", idempotent=True),
            operation,
            lambda exc: FailureSignal(FailureClass.CONTRADICTORY_EVIDENCE, idempotent=True),
            replan=replan,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.actions, ("replan",))

    def test_policy_denial_never_retries(self):
        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            raise PermissionError("denied")

        result = self.executor().execute(
            OperationSpec("protected-write"),
            operation,
            lambda exc: FailureSignal(FailureClass.POLICY_DENIED),
        )
        self.assertFalse(result.success)
        self.assertTrue(result.safe_stop)
        self.assertEqual(calls, 1)
        self.assertEqual(result.actions, ("escalate",))

    def test_attempt_budget_is_hard_boundary(self):
        result = self.executor(attempts=1).execute(
            OperationSpec("bounded-read", idempotent=True),
            lambda: (_ for _ in ()).throw(TimeoutError("timeout")),
            lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
        )
        self.assertFalse(result.success)
        self.assertTrue(result.safe_stop)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.actions, ("escalate",))

    def test_missing_required_recovery_callback_stops_safely(self):
        result = self.executor().execute(
            OperationSpec("research-read", idempotent=True),
            lambda: (_ for _ in ()).throw(RuntimeError("stale")),
            lambda exc: FailureSignal(FailureClass.STALE_CONTEXT, idempotent=True),
        )
        self.assertFalse(result.success)
        self.assertTrue(result.safe_stop)
        self.assertEqual(result.recovered_by, "refresh_context")

    def test_callback_failure_stops_safely(self):
        result = self.executor().execute(
            OperationSpec("research-read", idempotent=True),
            lambda: (_ for _ in ()).throw(RuntimeError("stale")),
            lambda exc: FailureSignal(FailureClass.STALE_CONTEXT, idempotent=True),
            refresh_context=lambda: (_ for _ in ()).throw(RuntimeError("refresh unavailable")),
        )
        self.assertFalse(result.success)
        self.assertTrue(result.safe_stop)
        self.assertEqual(result.recovered_by, "refresh_context_failed")

    def test_trace_contains_control_metadata_not_exception_payload(self):
        tracer = _Tracer()
        executor = RecoveryExecutor(
            RecoveryPolicy(RecoveryBudget(max_attempts=1, max_tool_calls=2, max_elapsed_seconds=5)),
            tracer=tracer,
        )
        secret = "credential=DO-NOT-TRACE"
        executor.execute(
            OperationSpec("safe-name", idempotent=True),
            lambda: (_ for _ in ()).throw(TimeoutError(secret)),
            lambda exc: FailureSignal(FailureClass.TIMEOUT, idempotent=True),
        )
        raw = repr(tracer.events)
        self.assertNotIn(secret, raw)
        self.assertIn("safe-name", raw)
        self.assertIn("timeout", raw)

    def test_operation_name_must_not_be_blank(self):
        with self.assertRaises(ValueError):
            OperationSpec("   ")


if __name__ == "__main__":
    unittest.main()
