import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.reliability import (
    FailureClass,
    FailureSignal,
    RecoveryAction,
    RecoveryBudget,
    RecoveryPolicy,
    RecoveryState,
    ReliabilityOutcome,
    summarize_reliability,
)


class TestRecoveryPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = RecoveryPolicy(
            RecoveryBudget(max_attempts=3, max_tool_calls=5, max_elapsed_seconds=30)
        )

    def test_timeout_retries_only_when_idempotent(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.TIMEOUT, idempotent=True),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=3),
        )
        self.assertEqual(decision.action, RecoveryAction.RETRY)
        self.assertTrue(decision.requires_verification)

    def test_uncertain_side_effect_requires_verify_before_retry(self):
        decision = self.policy.decide(
            FailureSignal(
                FailureClass.TIMEOUT,
                side_effect_uncertain=True,
                idempotent=False,
            ),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=3),
        )
        self.assertEqual(decision.action, RecoveryAction.VERIFY_BEFORE_RETRY)
        self.assertTrue(decision.requires_verification)

    def test_partial_state_requires_verify_before_retry(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.PARTIAL_STATE),
            RecoveryState(attempts=1, tool_calls=2, elapsed_seconds=5),
        )
        self.assertEqual(decision.action, RecoveryAction.VERIFY_BEFORE_RETRY)

    def test_verified_partial_state_replans_from_observed_state(self):
        decision = self.policy.decide(
            FailureSignal(
                FailureClass.PARTIAL_STATE,
                postcondition_verified=True,
            ),
            RecoveryState(attempts=1, tool_calls=2, elapsed_seconds=5),
        )
        self.assertEqual(decision.action, RecoveryAction.REPLAN)
        self.assertFalse(decision.requires_verification)

    def test_non_idempotent_transient_failure_uses_alternative_path(self):
        decision = self.policy.decide(
            FailureSignal(
                FailureClass.UPSTREAM_UNAVAILABLE,
                idempotent=False,
                has_alternative=True,
            ),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=2),
        )
        self.assertEqual(decision.action, RecoveryAction.REPLAN)

    def test_non_idempotent_transient_without_alternative_escalates(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.RATE_LIMIT, idempotent=False),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=2),
        )
        self.assertEqual(decision.action, RecoveryAction.ESCALATE)
        self.assertFalse(decision.automatic)

    def test_malformed_arguments_are_repaired_not_blindly_retried(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.MALFORMED_ARGUMENTS),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=1),
        )
        self.assertEqual(decision.action, RecoveryAction.REPAIR_ARGUMENTS)

    def test_stale_context_refreshes_before_continuing(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.STALE_CONTEXT),
            RecoveryState(attempts=1, tool_calls=1, elapsed_seconds=1),
        )
        self.assertEqual(decision.action, RecoveryAction.REFRESH_CONTEXT)

    def test_verification_failure_replans_when_budget_remains(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.VERIFICATION_FAILED),
            RecoveryState(attempts=1, tool_calls=2, elapsed_seconds=5),
        )
        self.assertEqual(decision.action, RecoveryAction.REPLAN)
        self.assertTrue(decision.requires_verification)

    def test_verification_failure_escalates_at_budget_boundary(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.VERIFICATION_FAILED),
            RecoveryState(attempts=2, tool_calls=2, elapsed_seconds=5),
        )
        self.assertEqual(decision.action, RecoveryAction.ESCALATE)
        self.assertFalse(decision.automatic)

    def test_policy_denial_is_never_automatic_retry(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.POLICY_DENIED),
            RecoveryState(),
        )
        self.assertEqual(decision.action, RecoveryAction.ESCALATE)
        self.assertFalse(decision.automatic)

    def test_budget_exhaustion_abstains_without_human_gate(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.TIMEOUT, idempotent=True),
            RecoveryState(attempts=3, tool_calls=3, elapsed_seconds=5),
            human_gate_available=False,
        )
        self.assertEqual(decision.action, RecoveryAction.ABSTAIN)
        self.assertFalse(decision.automatic)

    def test_unknown_failure_gets_one_replan_then_escalates(self):
        first = self.policy.decide(
            FailureSignal(FailureClass.UNKNOWN),
            RecoveryState(attempts=0, tool_calls=0, elapsed_seconds=0),
        )
        second = self.policy.decide(
            FailureSignal(FailureClass.UNKNOWN),
            RecoveryState(attempts=1, tool_calls=0, elapsed_seconds=1),
        )
        self.assertEqual(first.action, RecoveryAction.REPLAN)
        self.assertEqual(second.action, RecoveryAction.ESCALATE)

    def test_trace_fields_do_not_include_tool_payload(self):
        decision = self.policy.decide(
            FailureSignal(FailureClass.TIMEOUT, idempotent=True),
            RecoveryState(attempts=1, tool_calls=2, elapsed_seconds=2),
        )
        fields = decision.trace_fields()
        self.assertEqual(fields["recovery_action"], "retry")
        self.assertNotIn("payload", fields)
        self.assertNotIn("prompt", fields)

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            RecoveryBudget(max_attempts=0)
        with self.assertRaises(ValueError):
            RecoveryBudget(max_tool_calls=0)
        with self.assertRaises(ValueError):
            RecoveryBudget(max_elapsed_seconds=0)


class TestReliabilitySummary(unittest.TestCase):
    def test_summary_tracks_production_reliability_dimensions(self):
        summary = summarize_reliability([
            ReliabilityOutcome(True, attempts=1, tool_calls=2),
            ReliabilityOutcome(True, duplicate_action=True, attempts=2, tool_calls=3),
            ReliabilityOutcome(False, silent_failure=True, attempts=3, tool_calls=4),
            ReliabilityOutcome(False, attempts=2, tool_calls=2),
        ])
        self.assertEqual(summary.runs, 4)
        self.assertEqual(summary.success_rate, 0.5)
        self.assertEqual(summary.silent_failure_rate, 0.25)
        self.assertEqual(summary.duplicate_action_rate, 0.25)
        self.assertEqual(summary.mean_attempts, 2.0)
        self.assertEqual(summary.mean_tool_calls, 2.75)

    def test_empty_summary_is_defined(self):
        summary = summarize_reliability([])
        self.assertEqual(summary.runs, 0)
        self.assertEqual(summary.success_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
