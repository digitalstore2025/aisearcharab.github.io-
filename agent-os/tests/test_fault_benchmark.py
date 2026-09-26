import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.fault_benchmark import (
    SCENARIOS,
    Strategy,
    run_benchmark,
    simulate_case,
    wilson_interval,
)


class TestFaultBenchmark(unittest.TestCase):
    def scenario(self, name):
        return next(s for s in SCENARIOS if s.id == name)

    def test_scenario_set_is_complete_and_unique(self):
        ids = [s.id for s in SCENARIOS]
        self.assertEqual(len(ids), 9)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {
            "timeout_after_dispatch",
            "rate_limit",
            "partial_state",
            "malformed_arguments",
            "stale_evidence",
            "contradictory_evidence",
            "delayed_visibility",
            "policy_denial",
            "irreversible_side_effect_ambiguity",
        })

    def test_retry_only_duplicates_timeout_after_dispatch(self):
        result = simulate_case(
            self.scenario("timeout_after_dispatch"),
            Strategy.RETRY_ONLY,
            seed=1,
        )
        self.assertTrue(result.duplicate_action)
        self.assertFalse(result.success)

    def test_bounded_policy_stops_when_verification_is_unavailable(self):
        result = simulate_case(
            self.scenario("timeout_after_dispatch"),
            Strategy.BOUNDED,
            seed=1,
        )
        self.assertTrue(result.safe_stop)
        self.assertFalse(result.duplicate_action)
        self.assertEqual(result.final_action, "verification_unavailable_safe_stop")

    def test_verified_policy_avoids_duplicate_and_recovers_timeout_after_dispatch(self):
        result = simulate_case(
            self.scenario("timeout_after_dispatch"),
            Strategy.BOUNDED_VERIFIED,
            seed=1,
        )
        self.assertTrue(result.success)
        self.assertFalse(result.duplicate_action)
        self.assertEqual(result.final_action, "postcondition_verified")

    def test_malformed_arguments_are_not_fixed_by_retry_only(self):
        retry = simulate_case(
            self.scenario("malformed_arguments"),
            Strategy.RETRY_ONLY,
            seed=1,
        )
        bounded = simulate_case(
            self.scenario("malformed_arguments"),
            Strategy.BOUNDED,
            seed=1,
        )
        self.assertFalse(retry.success)
        self.assertTrue(bounded.success)
        self.assertEqual(bounded.final_action, "repair_arguments")

    def test_stale_evidence_creates_silent_baseline_failure_but_refresh_recovers(self):
        baseline = simulate_case(
            self.scenario("stale_evidence"),
            Strategy.NO_RECOVERY,
            seed=1,
        )
        bounded = simulate_case(
            self.scenario("stale_evidence"),
            Strategy.BOUNDED,
            seed=1,
        )
        self.assertTrue(baseline.silent_failure)
        self.assertTrue(bounded.success)
        self.assertEqual(bounded.final_action, "refresh_context")

    def test_policy_denial_is_safe_for_no_recovery_and_bounded_strategies(self):
        scenario = self.scenario("policy_denial")
        baseline = simulate_case(scenario, Strategy.NO_RECOVERY, seed=1)
        bounded = simulate_case(scenario, Strategy.BOUNDED, seed=1)
        verified = simulate_case(scenario, Strategy.BOUNDED_VERIFIED, seed=1)
        retry = simulate_case(scenario, Strategy.RETRY_ONLY, seed=1)
        self.assertTrue(baseline.success)
        self.assertTrue(bounded.success)
        self.assertTrue(verified.success)
        self.assertFalse(retry.success)
        self.assertEqual(retry.final_action, "unsafe_policy_retry")

    def test_seeded_benchmark_is_reproducible(self):
        first = run_benchmark(repeats=7, seed=42)
        second = run_benchmark(repeats=7, seed=42)
        self.assertEqual(first, second)

    def test_benchmark_reports_all_strategies_and_scenarios(self):
        report = run_benchmark(repeats=3, seed=42)
        self.assertEqual(report["scenario_count"], 9)
        self.assertEqual(set(report["aggregate"]), {s.value for s in Strategy})
        self.assertEqual(set(report["by_scenario"]), {s.id for s in SCENARIOS})
        for strategy in Strategy:
            self.assertEqual(report["aggregate"][strategy.value]["runs"], 27)

    def test_verified_recovery_reduces_duplicate_and_silent_failures_vs_retry_only(self):
        report = run_benchmark(repeats=20, seed=20260926)
        retry = report["aggregate"][Strategy.RETRY_ONLY.value]
        verified = report["aggregate"][Strategy.BOUNDED_VERIFIED.value]
        self.assertLess(verified["duplicate_action_rate"], retry["duplicate_action_rate"])
        self.assertLess(verified["silent_failure_rate"], retry["silent_failure_rate"])

    def test_bounded_recovery_does_not_require_verifier_for_repairable_arguments(self):
        report = run_benchmark(repeats=5, seed=17)
        bounded = report["by_scenario"]["malformed_arguments"][Strategy.BOUNDED.value]
        verified = report["by_scenario"]["malformed_arguments"][Strategy.BOUNDED_VERIFIED.value]
        self.assertEqual(bounded["success_rate"], 1.0)
        self.assertEqual(verified["success_rate"], 1.0)

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(8, 10)
        self.assertLessEqual(low, 0.8)
        self.assertGreaterEqual(high, 0.8)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)

    def test_empty_or_invalid_benchmark_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            run_benchmark(repeats=0)
        with self.assertRaises(ValueError):
            run_benchmark(repeats=1, scenarios=[])


if __name__ == "__main__":
    unittest.main()
