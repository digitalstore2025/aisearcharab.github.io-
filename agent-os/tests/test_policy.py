import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.policy import PolicyEngine
from agent_os.types import Action, Decision


class TestPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PolicyEngine.from_file(ROOT / "config/policies/default.json")

    def test_default_deny(self):
        self.assertEqual(self.engine.evaluate(Action("unknown", environment="local")).decision, Decision.DENY)

    def test_local_tests_allowed(self):
        self.assertEqual(self.engine.evaluate(Action("test.run", environment="local")).decision, Decision.ALLOW)

    def test_prod_deploy_approval(self):
        self.assertEqual(self.engine.evaluate(Action("deploy.production", environment="production")).decision, Decision.APPROVAL)

    def test_secret_read_denied(self):
        self.assertEqual(self.engine.evaluate(Action("secret.read", environment="local")).decision, Decision.DENY)

    def test_feature_branch_write_allowed(self):
        result = self.engine.evaluate(Action("repo.write", environment="development"))
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_pr_merge_requires_approval(self):
        result = self.engine.evaluate(Action("pr.merge", environment="development"))
        self.assertEqual(result.decision, Decision.APPROVAL)
