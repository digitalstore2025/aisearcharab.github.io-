import sys
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

    def test_security_task_adds_security_verifier(self):
        plan = self.planner.plan("Review auth secrets and prompt injection before release", complexity="high", risk="high")
        self.assertIn("security-redteam", plan.agents)
        self.assertTrue(any(a.independent for a in plan.assignments))

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
