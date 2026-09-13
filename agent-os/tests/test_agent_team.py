import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.agent_registry import AgentRegistry
from agent_os.team import TeamPlanner


class TestAgentTeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = AgentRegistry.from_file(ROOT / "config/agents/registry.json")
        cls.planner = TeamPlanner(cls.registry)

    def test_each_agent_has_operating_instructions(self):
        self.assertTrue(all(agent.instructions.strip() for agent in self.registry.agents))

    def test_registry_has_single_coordinator_and_reviewer(self):
        self.assertEqual(self.registry.coordinator.name, "execution-coordinator")
        self.assertEqual(self.registry.reviewer.name, "independent-reviewer")

    def test_rag_task_routes_ai_and_data(self):
        plan = self.planner.plan("Improve RAG retrieval eval and citation grounding", complexity="high")
        self.assertIn("ai-rag", plan.agents)
        self.assertIn("data-evals", plan.agents)
        self.assertIn("qa-reliability", plan.agents)
        self.assertEqual(plan.agents[-1], "independent-reviewer")

    def test_medium_risk_security_task_still_adds_security_verifier(self):
        plan = self.planner.plan("Audit auth token handling", complexity="medium", risk="medium")
        self.assertIn("security-redteam", plan.agents)

    def test_portfolio_task_builds_cross_functional_team(self):
        plan = self.planner.plan("Complete the AISearch platform end-to-end", complexity="critical", risk="high")
        expected = {
            "execution-coordinator", "product-strategy", "software-architect", "backend-platform",
            "frontend-accessibility", "ai-rag", "data-evals", "research-osint", "seo-geo",
            "devops-release", "qa-reliability", "security-redteam", "independent-reviewer",
        }
        self.assertEqual(set(plan.agents), expected)
        self.assertTrue(plan.portfolio_mode)
        self.assertLessEqual(max(len(w) for w in plan.waves), 4)

    def test_platform_word_alone_does_not_activate_portfolio(self):
        plan = self.planner.plan("Fix platform API bug", complexity="medium", risk="medium")
        self.assertFalse(plan.portfolio_mode)
        self.assertEqual(
            set(plan.agents),
            {"execution-coordinator", "software-architect", "backend-platform", "qa-reliability", "independent-reviewer"},
        )

    def test_profile_tool_allowlist_limits_agent_tools(self):
        plan = self.planner.plan(
            "Complete the AISearch platform end-to-end",
            complexity="critical",
            risk="high",
            profile_allowed_tools=("repo", "tests"),
        )
        self.assertTrue(all(set(a.allowed_tools) <= {"repo", "tests"} for a in plan.assignments))

    def test_invalid_risk_fails_closed(self):
        with self.assertRaises(ValueError):
            self.planner.plan("test", risk="urgent")

    def test_review_handoffs_receive_evidence(self):
        plan = self.planner.plan("Implement backend API and tests", complexity="high")
        edges = {(h.source, h.target, h.artifact) for h in plan.handoffs}
        self.assertIn(("backend-platform", "independent-reviewer", "evidence-and-open-risks"), edges)

    def test_assignments_include_operating_instructions(self):
        plan = self.planner.plan("Implement backend API", complexity="medium")
        coordinator = next(a for a in plan.assignments if a.agent == "execution-coordinator")
        reviewer = next(a for a in plan.assignments if a.agent == "independent-reviewer")
        self.assertTrue(coordinator.instructions)
        self.assertTrue(reviewer.instructions)
        self.assertTrue(reviewer.independent)

    def test_registry_rejects_string_boolean_portfolio(self):
        data = json.loads((ROOT / "config/agents/registry.json").read_text(encoding="utf-8"))
        data["agents"][0]["portfolio"] = "false"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "registry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON boolean"):
                AgentRegistry.from_file(path)

    def test_registry_rejects_non_string_trigger(self):
        data = json.loads((ROOT / "config/agents/registry.json").read_text(encoding="utf-8"))
        data["agents"][1]["triggers"] = ["product", 7]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "registry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-empty strings"):
                AgentRegistry.from_file(path)
