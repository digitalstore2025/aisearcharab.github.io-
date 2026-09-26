#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seo_router import route_task  # noqa: E402


POLICY = {
    "project_id": "aisearcharab",
    "min_quality": 0.90,
    "min_evidence": 1,
    "max_task_cost_usd": 5.0,
    "routes": {
        "deterministic": ["technical_seo_checks", "duplicate_detection", "gsc_threshold_routing", "sitemap_validation"],
        "ai_workflow": ["search_intent", "entity_extraction", "content_gap", "brief_generation", "anchor_suggestion", "geo_ai_search"],
        "agentic": ["traffic_loss_diagnosis", "indexation_diagnosis", "cannibalization_investigation"],
    },
    "human_approval_actions": ["publish", "production_deploy", "delete", "301", "410", "canonical_change"],
    "blocked_autonomous_actions": ["auto_publish", "auto_delete", "auto_301", "auto_410", "auto_canonical_change"],
}


class SeoRouterTests(unittest.TestCase):
    def test_semantic_task_routes_to_ai_workflow(self) -> None:
        decision = route_task(
            POLICY,
            {
                "task_id": "intent-001",
                "task_type": "search_intent",
                "semantic_needed": True,
                "evidence": [{"type": "gsc_export", "ref": "fixture"}],
            },
        )
        self.assertEqual(decision.route, "ai_workflow")
        self.assertFalse(decision.human_approval_required)
        self.assertFalse(decision.failures)

    def test_title_signal_routes_to_deterministic(self) -> None:
        decision = route_task(
            POLICY,
            {
                "task_id": "tech-001",
                "page_signals": {"title_length": 24},
                "evidence": [{"type": "crawl", "ref": "fixture"}],
            },
        )
        self.assertEqual(decision.route, "deterministic")
        self.assertEqual(decision.workflow, "technical_seo_checks")

    def test_unindexed_page_routes_to_agentic_diagnosis(self) -> None:
        decision = route_task(
            POLICY,
            {
                "task_id": "index-001",
                "metrics": {"indexed": False},
                "evidence": [{"type": "index_coverage", "ref": "fixture"}],
            },
        )
        self.assertEqual(decision.route, "agentic")
        self.assertEqual(decision.workflow, "indexation_diagnosis")

    def test_human_approval_action_is_manual_review(self) -> None:
        decision = route_task(
            POLICY,
            {
                "task_id": "canon-001",
                "task_type": "technical_seo_checks",
                "requested_action": "canonical_change",
                "evidence": [{"type": "crawl", "ref": "fixture"}],
            },
        )
        self.assertEqual(decision.route, "manual_review")
        self.assertTrue(decision.human_approval_required)

    def test_blocked_autonomous_action_is_blocked(self) -> None:
        decision = route_task(
            POLICY,
            {
                "task_id": "delete-001",
                "requested_action": "auto_delete",
                "evidence": [{"type": "crawl", "ref": "fixture"}],
            },
        )
        self.assertTrue(decision.blocked)
        self.assertEqual(decision.route, "blocked")


if __name__ == "__main__":
    unittest.main()
