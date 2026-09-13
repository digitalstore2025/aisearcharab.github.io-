import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.mcp_gateway import MCPGateway
from agent_os.policy import PolicyEngine
from agent_os.tool_runtime import PolicyBoundToolRuntime, RegisteredToolExecutor
from agent_os.types import Action, ToolCall, TrustLevel, validate_execution_environment


class TestEnvironmentBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = PolicyEngine.from_file(ROOT / "config/policies/default.json")

    def test_only_canonical_environment_labels_are_accepted(self):
        for environment in ("local", "development", "staging", "production"):
            with self.subTest(environment=environment):
                self.assertEqual(validate_execution_environment(environment), environment)

        for environment in ("prod", "Production", "production ", "", "sandbox", None):
            with self.subTest(environment=environment):
                with self.assertRaises(ValueError):
                    validate_execution_environment(environment)  # type: ignore[arg-type]

    def test_policy_wildcards_cannot_authorize_unknown_environment(self):
        for environment in ("prod", "Production", "production ", "sandbox"):
            with self.subTest(environment=environment):
                with self.assertRaises(ValueError):
                    self.policy.evaluate(
                        Action(name="repo.read", resource="repo", environment=environment)
                    )

    def test_gateway_denies_unknown_environment_before_policy_allow(self):
        gateway = MCPGateway(self.policy)
        call = ToolCall("repo", "repo.read", {}, TrustLevel.TRUSTED)
        for environment in ("prod", "Production", "production ", "sandbox"):
            with self.subTest(environment=environment):
                result = gateway.authorize(call, environment=environment)
                self.assertFalse(result.allowed)
                self.assertFalse(result.approval_required)
                self.assertEqual(result.rule_id, "invalid-environment")

    def test_tool_handler_never_runs_for_unknown_environment(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.write",
            handler=lambda args: executed.append(args) or "changed",
        )
        runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("repo",),
            production_mutations=True,
        )
        call = ToolCall("repo", "repo.write", {"path": "x"}, TrustLevel.TRUSTED)

        for environment in ("prod", "Production", "production ", "sandbox"):
            with self.subTest(environment=environment):
                result = runtime.run(call, environment=environment)
                self.assertEqual(result.status, "denied")
                self.assertEqual(result.rule_id, "invalid-environment")
        self.assertEqual(executed, [])

    def test_canonical_development_behavior_is_preserved(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.write",
            handler=lambda args: executed.append(args) or "changed",
        )
        runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("repo",),
            production_mutations=True,
        )
        result = runtime.run(
            ToolCall("repo", "repo.write", {"path": "x"}, TrustLevel.TRUSTED),
            environment="development",
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(executed, [{"path": "x"}])


if __name__ == "__main__":
    unittest.main()
