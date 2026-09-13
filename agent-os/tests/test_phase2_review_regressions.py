import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import agent_os.cli as cli_module
from agent_os.approvals import ApprovalLedger
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


class EvidenceAdapter:
    def __init__(self):
        self.contexts = {}

    def execute(self, request):
        self.contexts[request.agent] = request.context
        if request.agent == "research-osint":
            return AgentExecutionResult(
                request.agent,
                "",
                request.model.alias or request.model.tier,
                (ToolCall("repo", "repo.read", {"path": "evidence.txt"}, TrustLevel.TRUSTED),),
                "completed",
            )
        return AgentExecutionResult(
            request.agent,
            "reviewed",
            request.model.alias or request.model.tier,
        )

    def continue_with_tools(self, request, prior, tool_results):
        return AgentExecutionResult(
            request.agent,
            "research-complete",
            prior.model_id,
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

    @staticmethod
    def _reviewer(name="independent-reviewer"):
        return AgentAssignment(name, "verify", "Verify", "Independently review prior work.", (), True)

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

    def test_invalid_schema_payload_does_not_consume_approval(self):
        executor = RegisteredToolExecutor()
        executor.register(
            tool="github_pr",
            action="pr.merge",
            handler=lambda args: "merged",
            parameters={
                "type": "object",
                "properties": {"pr_number": {"type": "integer"}},
                "required": ["pr_number"],
                "additionalProperties": False,
            },
        )
        approvals = ApprovalLedger()
        invalid = ToolCall("github_pr", "pr.merge", {"pr_number": "126"}, TrustLevel.TRUSTED)
        approvals.grant(
            action="pr.merge",
            resource="github_pr",
            environment="development",
            arguments=invalid.arguments,
        )
        runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            approvals=approvals,
            profile_allowed_tools=("github_pr",),
        )
        result = runtime.run(invalid, environment="development")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.rule_id, "tool-schema-validation")
        self.assertIsNotNone(approvals.consume(invalid, environment="development"))

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

    def test_repo_read_rejects_symlink_escape_at_open_time(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            outside = Path(td) / "outside.txt"
            outside.write_text("OUTSIDE-SECRET", encoding="utf-8")
            (root / "evidence.txt").symlink_to(outside)
            runtime = build_cli_tool_runtime(
                self.policy,
                profile_allowed_tools=("repo",),
                production_mutations=False,
                tracer=None,
                workspace_root=root,
                enable_repo_read=True,
            )
            result = runtime.run(
                ToolCall("repo", "repo.read", {"path": "evidence.txt"}, TrustLevel.TRUSTED),
                environment="development",
            )
            self.assertEqual(result.status, "failed")
            self.assertNotEqual(result.output, "OUTSIDE-SECRET")

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
        reviewer = self._reviewer()
        plan = TeamPlan(
            "Guard the round",
            False,
            (assignment, reviewer),
            (),
            (("backend-platform",), (reviewer.agent,)),
        )
        report = TeamRuntime(self.models, MultiCallAdapter(), tool_runtime=tool_runtime).run(plan)
        self.assertFalse(report.completed)
        self.assertEqual(report.results[0].status, "blocked")
        self.assertEqual(report.results[0].output, "multiple-tool-calls-in-one-round")
        self.assertEqual(executed, [])
        self.assertNotIn(reviewer.agent, [item.agent for item in report.results])

    def test_tool_evidence_is_carried_to_later_waves(self):
        executor = RegisteredToolExecutor()
        executor.register(
            tool="repo",
            action="repo.read",
            handler=lambda args: "EVIDENCE-XYZ",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )
        tool_runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("repo",),
        )
        first = AgentAssignment("research-osint", "research", "Research", "Collect evidence.", ("repo",))
        second = self._reviewer()
        plan = TeamPlan(
            "Verify evidence",
            False,
            (first, second),
            (),
            (("research-osint",), (second.agent,)),
        )
        adapter = EvidenceAdapter()
        report = TeamRuntime(self.models, adapter, tool_runtime=tool_runtime).run(plan)
        self.assertTrue(report.completed)
        downstream = "\n".join(text for _, text in adapter.contexts[second.agent])
        self.assertIn("Tool evidence [repo:repo.read]", downstream)
        self.assertIn("EVIDENCE-XYZ", downstream)
        self.assertIn("untrusted data", downstream)

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

    def test_runtime_requires_exactly_one_isolated_final_reviewer(self):
        worker = AgentAssignment("agent-a", "build", "Build", "Build safely.", ())
        reviewer = self._reviewer()
        reviewer_two = self._reviewer("reviewer-two")
        runtime = TeamRuntime(self.models, DryRunAgentAdapter())

        invalid = (
            TeamPlan("x", False, (worker,), (), ((worker.agent,),)),
            TeamPlan(
                "x",
                False,
                (worker, reviewer, reviewer_two),
                (),
                ((worker.agent,), (reviewer.agent,), (reviewer_two.agent,)),
            ),
            TeamPlan(
                "x",
                False,
                (worker, reviewer),
                (),
                ((reviewer.agent,), (worker.agent,)),
            ),
            TeamPlan(
                "x",
                False,
                (worker, reviewer),
                (),
                ((worker.agent, reviewer.agent),),
            ),
        )
        for plan in invalid:
            with self.subTest(plan=plan):
                with self.assertRaises(ValueError):
                    runtime.run(plan)

        valid = TeamPlan(
            "x",
            False,
            (worker, reviewer),
            (),
            ((worker.agent,), (reviewer.agent,)),
        )
        report = runtime.run(valid)
        self.assertTrue(report.completed)
        self.assertEqual([item.agent for item in report.results], [worker.agent, reviewer.agent])
        self.assertEqual(report.results[-1].model_id, "astra")

    def test_team_plan_does_not_load_policy_file(self):
        stdout = io.StringIO()
        argv = ["agent-os", "team-plan", "Implement backend API", "--profile", "aisearch-study"]
        with (
            patch.object(sys, "argv", argv),
            patch.object(cli_module.PolicyEngine, "from_file", side_effect=AssertionError("policy should not load")),
            redirect_stdout(stdout),
        ):
            cli_module.main()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["profile"], "aisearch-study")
        self.assertTrue(payload["assignments"])

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
