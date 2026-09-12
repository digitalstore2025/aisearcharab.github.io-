import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.model_router import ModelRouter
from agent_os.skill_registry import SkillRegistry


class TestRoutingModels(unittest.TestCase):
    def test_skill_routing(self):
        registry = SkillRegistry.from_file(ROOT / "config/skills/registry.json")
        got = [s.name for s in registry.route("Review auth security before production release")]
        self.assertIn("security-review", got)
        self.assertIn("release-readiness", got)

    def test_critical_model_has_verifier(self):
        router = ModelRouter.from_file(ROOT / "config/models/catalog.json")
        choice = router.choose(complexity="high", risk="critical", requires_tools=True)
        self.assertEqual(choice.tier, "critical")
        self.assertIn("verifier", choice.model)
