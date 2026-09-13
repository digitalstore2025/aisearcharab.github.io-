import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.cli_tools import build_cli_tool_runtime
from agent_os.mcp_gateway import MCPGateway
from agent_os.model_router import ModelRouter
from agent_os.policy import PolicyEngine
from agent_os.provider_adapter import AgentExecutionRequest, AgentExecutionResult, DryRunAgentAdapter, OpenAIResponsesAdapter
from agent_os.runtime import TeamRuntime
from agent_os.team import AgentAssignment, TeamPlan
from agent_os.tool_runtime import PolicyBoundToolRuntime, RegisteredToolExecutor
from agent_os.types import ToolCall, TrustLevel


class MultiCallAdapter:
    def execute(self, request):
        return AgentExecutionResult(
            request.agent,
            "",
            request.model.alias or request.model.tier,
            (
                ToolCall("repo", "repo.read", {"path": "README.md"}, TrustLevel.TRUSTED),
                ToolCall("tests", "test.run", {}, TrustLevel.TRUSTED),
            ),
            "completed",
        )


class FakeResponse:
    output_text = "ok"
    output = []
    status = "completed"


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class TestPhase2ReviewRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = ModelRouter.from_file(ROOT / "config/models/catalog.json")
        cls.policy = PolicyEngine.from_file(ROOT / "config/policies/default.json")

    def test_null_policy_alias_is_rejected(self):
        router = ModelRouter({
            "tiers": {
                "economy": {
                    "model": "placeholder",
                    "policy_alias": None,
                    "tool_capable": True,
                }
            }
        })
        with self.assertRaisesRegex(ValueError, "policy_alias"):
            router.choose(complexity="low", risk="low")

    def test_tool_arguments_are_schema_validated_before_handler(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.read",
            handler=lambda args: executed.append(args) or "ok",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1}},
                "required": ["path"],
                "additionalProperties": False,
            },
            strict=True,
        )

        for arguments in ({}, {"path": 123}, {"path": "README.md", "extra": True}):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    executor.execute(ToolCall("repo", "repo.read", arguments, TrustLevel.TRUSTED))
        self.assertEqual(executed, [])
        self.assertEqual(
            executor.execute(ToolCall("repo", "repo.read", {"path": "README.md"}, TrustLevel.TRUSTED)),
            "ok",
        )
        self.assertEqual(executed, [{"path": "README.md"}])

    def test_unsupported_schema_keyword_fails_registration(self):
        executor = RegisteredToolExecutor()
        with self.assertRaisesRegex(ValueError, "Unsupported schema keyword"):
            executor.register(
                tool="repo",
                action="repo.read",
                handler=lambda args: "ok",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                    "oneOf": [],
                },
            )

    def test_sensitive_workspace_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sensitive_root = Path(td) / ".ssh"
            sensitive_root.mkdir()
            (sensitive_root / "id_rsa").write_text("PRIVATE", encoding="utf-8")
            with self.assertRaises(PermissionError):
                build_cli_tool_runtime(
                    self.policy,
                    profile_allowed_tools=("repo",),
                    production_mutations=False,
                    tracer=None,
                    workspace_root=sensitive_root,
                    enable_repo_read=True,
                )

    def test_multi_tool_round_is_blocked_before_any_handler_runs(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.read",
            handler=lambda args: executed.append("repo") or "content",
        )
        executor.register(
            tool="tests",
            action="test.run",
            handler=lambda args: executed.append("tests") or "passed",
        )
        tool_runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("repo", "tests"),
        )
        assignment = AgentAssignment(
            "backend-platform",
            "build",
            "Perform guarded work",
            "Use authorized tools only.",
            ("repo", "tests"),
        )
        plan = TeamPlan("Guard the round", False, (assignment,), (), (("backend-platform",),))
        report = TeamRuntime(self.models, MultiCallAdapter(), tool_runtime=tool_runtime).run(plan)
        self.assertFalse(report.completed)
        self.assertEqual(report.results[0].status, "blocked")
        self.assertEqual(report.results[0].output, "multiple-tool-calls-in-one-round")
        self.assertEqual(executed, [])

    def test_malformed_team_plans_fail_before_execution(self):
        first = AgentAssignment("agent-a", "build", "A", "A", ())
        duplicate = AgentAssignment("agent-a", "verify", "B", "B", ())
        second = AgentAssignment("agent-b", "build", "B", "B", ())
        runtime = TeamRuntime(self.models, DryRunAgentAdapter())

        cases = (
            TeamPlan("x", False, (first, duplicate), (), (("agent-a",),)),
            TeamPlan("x", False, (first,), (), (("agent-a", "agent-a"),)),
            TeamPlan("x", False, (first, second), (), (("agent-a",),)),
            TeamPlan("x", False, (first,), (), ((), ("agent-a",))),
        )
        for plan in cases:
            with self.subTest(plan=plan):
                with self.assertRaises(ValueError):
                    runtime.run(plan)

    def test_openai_adapter_disables_parallel_tool_calls(self):
        client = FakeClient()
        adapter = OpenAIResponsesAdapter(client=client)
        choice = self.models.choose(complexity="medium", risk="medium")
        request = AgentExecutionRequest(
            "backend-platform",
            "Read evidence",
            "Use one tool per round.",
            "Read repository evidence",
            (),
            choice,
            (),
        )
        # No tools means the provider flag is intentionally absent.
        with patch.dict(os.environ, {"ASTRA_MODEL_TERRA": "provider-model-123"}, clear=True):
            adapter.execute(request)
        self.assertNotIn("parallel_tool_calls", client.responses.calls[0])

        executor = RegisteredToolExecutor()
        definition = executor.register(
            tool="repo",
            action="repo.read",
            name="repo_read",
            handler=lambda args: "ok",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )
        client2 = FakeClient()
        adapter2 = OpenAIResponsesAdapter(client=client2)
        request2 = AgentExecutionRequest(
            "backend-platform",
            "Read evidence",
            "Use one tool per round.",
            "Read repository evidence",
            (),
            choice,
            (definition,),
        )
        with patch.dict(os.environ, {"ASTRA_MODEL_TERRA": "provider-model-123"}, clear=True):
            adapter2.execute(request2)
        self.assertIs(client2.responses.calls[0]["parallel_tool_calls"], False)


if __name__ == "__main__":
    unittest.main()
