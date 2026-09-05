from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "score_product_validation.py"
spec = importlib.util.spec_from_file_location("score_product_validation", MODULE_PATH)
assert spec and spec.loader
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

FIELDNAMES = [
    "evaluator_id",
    "task_id",
    "persona",
    "ais_mode",
    "query_source",
    "winner",
    "ais_task_success",
    "ais_retrieval_success",
    "ais_zero_result",
    "ais_citation_usefulness",
    "ais_citation_accuracy_pct",
    "ais_citation_completeness_pct",
    "ais_groundedness_pct",
    "ais_trust",
    "ais_completion_seconds",
    "would_return",
    "reason",
    "notes",
]


def row(evaluator: int, task: int, *, mode: str = "retrieval_only", success: int = 1):
    return {
        "evaluator_id": f"E{evaluator:02d}",
        "task_id": f"Q{task:03d}",
        "persona": "journalist",
        "ais_mode": mode,
        "query_source": "participant",
        "winner": "aisearcharab" if success else "chatgpt",
        "ais_task_success": str(success),
        "ais_retrieval_success": str(success),
        "ais_zero_result": "0" if success else "1",
        "ais_citation_usefulness": "5" if success else "2",
        "ais_citation_accuracy_pct": "100" if success else "50",
        "ais_citation_completeness_pct": "100" if success else "50",
        "ais_groundedness_pct": "100" if success else "50",
        "ais_trust": "5" if success else "2",
        "ais_completion_seconds": "12.5",
        "would_return": str(success),
        "reason": "fixture",
        "notes": "",
    }


class ProductValidationScorerTests(unittest.TestCase):
    def write_rows(self, rows):
        temp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        with temp:
            writer = csv.DictWriter(temp, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        return Path(temp.name)

    def test_small_sample_is_insufficient_evidence(self):
        path = self.write_rows([row(1, 1), row(2, 2), row(3, 3)])
        summary = score.summarize(score.load_rows(path))
        self.assertFalse(summary["measurement_ready"])
        self.assertEqual(summary["proposed_decision"], "INSUFFICIENT_EVIDENCE")

    def test_minimum_coverage_can_proceed(self):
        rows = []
        for i in range(30):
            evaluator = (i % 10) + 1
            task = (i % 10) + 1
            mode = "retrieval_only" if i < 15 else "generated_answer"
            rows.append(row(evaluator, task, mode=mode, success=1))
        path = self.write_rows(rows)
        summary = score.summarize(score.load_rows(path))
        self.assertTrue(summary["measurement_ready"])
        self.assertEqual(summary["proposed_decision"], "PROCEED")
        self.assertEqual(summary["zero_result_rate_pct"], 0.0)
        self.assertEqual(set(summary["by_mode"]), {"retrieval_only", "generated_answer"})

    def test_duplicate_evaluator_task_mode_is_rejected(self):
        path = self.write_rows([row(1, 1), row(1, 1)])
        with self.assertRaisesRegex(ValueError, "duplicate evaluator/task/mode"):
            score.load_rows(path)

    def test_percent_out_of_range_is_rejected(self):
        invalid = row(1, 1)
        invalid["ais_groundedness_pct"] = "101"
        path = self.write_rows([invalid])
        with self.assertRaisesRegex(ValueError, "ais_groundedness_pct"):
            score.load_rows(path)

    def test_wilson_interval_contains_point_estimate(self):
        low, high = score.wilson_interval(7, 10)
        self.assertLess(low, 70.0)
        self.assertGreater(high, 70.0)


if __name__ == "__main__":
    unittest.main()
