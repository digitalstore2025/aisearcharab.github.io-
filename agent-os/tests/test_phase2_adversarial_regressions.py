import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os.approvals import ApprovalLedger
from agent_os.mcp_gateway import MCPGateway
from agent_os.model_router import ModelRouter
from agent_os.policy import PolicyEngine
from agent_os.provider_adapter import AgentExecutionResult, DryRunAgentAdapter
from agent_os.runtime import TeamRuntime
from agent_os.team import AgentAssignment, Handoff, TeamPlan
from agent_os.tool_runtime import PolicyBoundToolRuntime, RegisteredToolExecutor
from agent_os.tracing import JsonlTracer
from agent_os.types import ToolCall, TrustLevel

ROOT = Path(__file__).resolve().parents[1]


class ToolOnlyAdapter:
    def execute(self, request):
        return AgentExecutionResult(
            request.agent,
            "",
            request.model.alias or request.model.tier,
            (ToolCall("repo", "repo.read", {"path": "README.md"}, TrustLevel.TRUSTED),),
            "completed",
        )


class ContextCaptureAdapter:
    def __init__(self):
        self.contexts = {}

    def execute(self, request):
        self.contexts[request.agent] = request.context
        return AgentExecutionResult(
            request.agent,
            f"output:{request.agent}",
            request.model.alias or request.model.tier,
        )


class TestPhase2AdversarialRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = ModelRouter.from_file(ROOT / "config/models/catalog.json")
        cls.policy = PolicyEngine.from_file(ROOT / "config/policies/default.json")

    @staticmethod
    def _worker(name="worker", tools=()):
        return AgentAssignment(name, "build", "Build", "Operate safely.", tuple(tools))

    @staticmethod
    def _reviewer(name="independent-reviewer"):
        return AgentAssignment(name, "verify", "Review", "Independently review evidence.", (), True)

    def test_non_object_tool_arguments_fail_closed(self):
        ledger = ApprovalLedger()
        with self.assertRaisesRegex(ValueError, "JSON object"):
            ledger.grant(
                action="repo.read",
                resource="repo",
                environment="development",
                arguments=[],  # type: ignore[arg-type]
            )

        malformed = ToolCall("repo", "repo.read", [], TrustLevel.TRUSTED)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "JSON object"):
            ledger.consume(malformed, environment="development")

        executor = RegisteredToolExecutor()
        executor.register(tool="repo", action="repo.read", handler=lambda args: "content")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            executor.validate(malformed)

    def test_adapter_without_continuation_cannot_execute_side_effect(self):
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
        worker = self._worker(tools=("repo",))
        reviewer = self._reviewer()
        plan = TeamPlan(
            "Read repository evidence",
            False,
            (worker, reviewer),
            (),
            ((worker.agent,), (reviewer.agent,)),
        )

        report = TeamRuntime(self.models, ToolOnlyAdapter(), tool_runtime=tool_runtime).run(plan)

        self.assertFalse(report.completed)
        self.assertEqual(report.results[0].status, "blocked")
        self.assertEqual(report.results[0].output, "adapter-does-not-support-tool-continuation")
        self.assertEqual(executed, [])
        self.assertNotIn(reviewer.agent, [item.agent for item in report.results])

    def test_context_follows_only_explicit_handoffs(self):
        alpha = self._worker("alpha")
        beta = self._worker("beta")
        reviewer = self._reviewer()
        plan = TeamPlan(
            "Route bounded evidence",
            False,
            (alpha, beta, reviewer),
            (Handoff("alpha", reviewer.agent, "alpha-evidence"),),
            ((alpha.agent, beta.agent), (reviewer.agent,)),
        )
        adapter = ContextCaptureAdapter()

        report = TeamRuntime(self.models, adapter).run(plan)

        self.assertTrue(report.completed)
        reviewer_context = "\n".join(text for _, text in adapter.contexts[reviewer.agent])
        self.assertIn("output:alpha", reviewer_context)
        self.assertIn("Handoff artifact [alpha-evidence]", reviewer_context)
        self.assertNotIn("output:beta", reviewer_context)
        self.assertEqual(adapter.contexts[alpha.agent], ())
        self.assertEqual(adapter.contexts[beta.agent], ())

    def test_invalid_handoff_graph_fails_before_execution(self):
        worker = self._worker()
        reviewer = self._reviewer()
        waves = ((worker.agent,), (reviewer.agent,))
        invalid_handoffs = (
            (Handoff("unknown", reviewer.agent, "evidence"),),
            (Handoff(worker.agent, "unknown", "evidence"),),
            (Handoff(worker.agent, worker.agent, "evidence"),),
            (Handoff(reviewer.agent, worker.agent, "backwards"),),
            (Handoff(worker.agent, reviewer.agent, "   "),),
            (
                Handoff(worker.agent, reviewer.agent, "evidence-a"),
                Handoff(worker.agent, reviewer.agent, "evidence-b"),
            ),
        )
        runtime = TeamRuntime(self.models, DryRunAgentAdapter())
        for handoffs in invalid_handoffs:
            with self.subTest(handoffs=handoffs):
                plan = TeamPlan("x", False, (worker, reviewer), handoffs, waves)
                with self.assertRaises(ValueError):
                    runtime.run(plan)

    def test_test_run_is_not_a_production_read_exemption(self):
        executed = []
        executor = RegisteredToolExecutor()
        executor.register(
            tool="tests",
            action="test.run",
            handler=lambda args: executed.append(args) or "ran",
        )
        runtime = PolicyBoundToolRuntime(
            MCPGateway(self.policy),
            executor,
            profile_allowed_tools=("tests",),
            production_mutations=False,
        )

        result = runtime.run(
            ToolCall("tests", "test.run", {}, TrustLevel.TRUSTED),
            environment="production",
        )

        self.assertEqual(result.status, "denied")
        self.assertEqual(result.rule_id, "profile-production-boundary")
        self.assertEqual(executed, [])

    def test_best_effort_trace_write_failure_does_not_fail_team(self):
        worker = self._worker()
        reviewer = self._reviewer()
        plan = TeamPlan(
            "Complete bounded work",
            False,
            (worker, reviewer),
            (),
            ((worker.agent,), (reviewer.agent,)),
        )
        with tempfile.TemporaryDirectory() as td:
            tracer = JsonlTracer(Path(td) / "trace.jsonl")
            with patch.object(Path, "open", side_effect=OSError("disk full")):
                report = TeamRuntime(self.models, DryRunAgentAdapter(), tracer=tracer).run(plan)

        self.assertTrue(report.completed)
        self.assertGreater(tracer.write_failures, 0)
        self.assertEqual(tracer.last_write_error, "OSError")

    def test_strict_trace_write_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as td:
            tracer = JsonlTracer(Path(td) / "trace.jsonl", strict=True)
            with patch.object(Path, "open", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    tracer.emit("test.event", status="completed")
        self.assertEqual(tracer.write_failures, 1)


if __name__ == "__main__":
    unittest.main()
