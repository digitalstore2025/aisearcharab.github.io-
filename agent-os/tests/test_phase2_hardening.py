import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.cli_tools import build_cli_tool_runtime
from agent_os.model_router import ModelRouter
from agent_os.policy import PolicyEngine
from agent_os.provider_adapter import AgentExecutionRequest, AgentExecutionResult, OpenAIResponsesAdapter
from agent_os.runtime import TeamRuntime
from agent_os.team import AgentAssignment, TeamPlan
from agent_os.tool_runtime import PolicyBoundToolRuntime, RegisteredToolExecutor
from agent_os.mcp_gateway import MCPGateway
from agent_os.types import ToolCall, ToolDefinition, TrustLevel


class FakeResponse:
    def __init__(self, *, status="completed", output_text="", output=()):
        self.status = status
        self.output_text = output_text
        self.output = list(output)


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


class FailedAdapterWithToolCall:
    def execute(self, request):
        return AgentExecutionResult(
            request.agent,
            "failed-provider-output",
            request.model.alias or request.model.tier,
            (ToolCall("repo", "repo.read", {"path": "README.md"}, TrustLevel.TRUSTED),),
            "failed",
        )


class TestPhase2Hardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = ModelRouter.from_file(ROOT / "config/models/catalog.json")
        cls.policy = PolicyEngine.from_file(ROOT / "config/policies/default.json")

    def test_failed_provider_response_discards_function_calls(self):
        response = FakeResponse(
            status="failed",
            output=({
                "type": "function_call",
                "name": "repo_read",
                "call_id": "call-failed",
                "arguments": '{"path":"README.md"}',
            },),
        )
        adapter = OpenAIResponsesAdapter(client=FakeClient(response))
        request = AgentExecutionRequest(
            "backend-platform",
            "Read evidence",
            "Use only authorized tools.",
            "Read README",
            (),
            self.models.choose(complexity="medium", risk="medium"),
            (ToolDefinition(
                "repo_read",
                "repo",
                "repo.read",
                "Read repo file",
                {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                True,
            ),),
        )
        with patch.dict(os.environ, {"ASTRA_MODEL_TERRA": "provider-model-123"}, clear=True):
            result = adapter.execute(request)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.tool_calls, ())

    def test_runtime_never_executes_calls_from_failed_adapter_result(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.read",
            handler=lambda args: executed.append(args) or "content",
        )
        tool_runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("repo",),
        )
        assignment = AgentAssignment(
            "backend-platform",
            "build",
            "Read evidence",
            "Use only authorized tools.",
            ("repo",),
        )
        plan = TeamPlan("Read README", False, (assignment,), (), (("backend-platform",),))
        report = TeamRuntime(
            self.models,
            FailedAdapterWithToolCall(),
            tool_runtime=tool_runtime,
        ).run(plan, complexity="medium", risk="medium")
        self.assertFalse(report.completed)
        self.assertEqual(executed, [])
        self.assertEqual(report.results[0].status, "failed")

    def test_cli_repo_read_is_opt_in_root_confined_and_sensitive_path_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "workspace"
            root.mkdir()
            (root / "README.md").write_text("safe-content", encoding="utf-8")
            (root / ".env").write_text("SECRET=value", encoding="utf-8")
            (base / "outside.txt").write_text("outside", encoding="utf-8")

            runtime = build_cli_tool_runtime(
                self.policy,
                profile_allowed_tools=("repo",),
                production_mutations=False,
                tracer=None,
                workspace_root=root,
                enable_repo_read=True,
            )
            definitions = runtime.definitions_for(("repo",))
            self.assertEqual([item.name for item in definitions], ["repo_read"])

            safe = runtime.run(
                ToolCall("repo", "repo.read", {"path": "README.md"}, TrustLevel.TRUSTED),
                environment="development",
            )
            self.assertEqual(safe.status, "completed")
            self.assertEqual(safe.output, "safe-content")

            sensitive = runtime.run(
                ToolCall("repo", "repo.read", {"path": ".env"}, TrustLevel.TRUSTED),
                environment="development",
            )
            self.assertEqual(sensitive.status, "failed")
            self.assertNotIn("SECRET=value", sensitive.reason)

            traversal = runtime.run(
                ToolCall("repo", "repo.read", {"path": "../outside.txt"}, TrustLevel.TRUSTED),
                environment="development",
            )
            self.assertEqual(traversal.status, "failed")
            self.assertNotIn("outside", str(traversal.output))

    def test_cli_tool_runtime_is_default_deny_without_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = build_cli_tool_runtime(
                self.policy,
                profile_allowed_tools=("repo",),
                production_mutations=False,
                tracer=None,
                workspace_root=td,
                enable_repo_read=False,
            )
            self.assertEqual(runtime.definitions_for(("repo",)), ())


if __name__ == "__main__":
    unittest.main()
