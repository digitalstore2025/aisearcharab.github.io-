import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.config import load_profile
from agent_os.model_router import ModelRouter
from agent_os.orchestrator import Orchestrator
from agent_os.policy import PolicyEngine
from agent_os.skill_registry import SkillRegistry
from agent_os.tracing import JsonlTracer


class TestHardeningRegressions(unittest.TestCase):
    def test_profile_defaults_and_constraints_apply_to_plan(self):
        profile = load_profile("aisearch-study", ROOT / "config")
        orchestrator = Orchestrator(
            SkillRegistry.from_file(ROOT / "config/skills/registry.json"),
            ModelRouter.from_file(ROOT / "config/models/catalog.json"),
            PolicyEngine.from_file(ROOT / "config/policies/default.json"),
        )
        plan = orchestrator.plan(
            "Review auth security before production release",
            complexity=profile.default_complexity,
            risk=profile.default_risk,
            profile=profile.name,
            profile_mode=profile.mode,
            allowed_tools=profile.allowed_tools,
            production_mutations=profile.production_mutations,
        )
        self.assertEqual(plan.model.tier, "strong")
        self.assertEqual(plan.mode, "shadow")
        self.assertIn("repo", plan.allowed_tools)
        self.assertFalse(plan.production_mutations)

    def test_profile_rejects_string_boolean(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "bad.json").write_text(json.dumps({
                "name": "bad",
                "mode": "shadow",
                "allowed_tools": ["repo"],
                "default_risk": "high",
                "default_complexity": "high",
                "production_mutations": "false",
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON boolean"):
                load_profile("bad", root)

    def test_tracer_does_not_persist_arbitrary_payload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trace.jsonl"
            tracer = JsonlTracer(path)
            event = tracer.emit("test", task="password=super-secret", tier="strong")
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("super-secret", raw)
            self.assertEqual(event.data["tier"], "strong")
            self.assertIn("task", event.data["redacted_fields"])

    def test_tracer_redacts_secret_inside_allowlisted_string(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trace.jsonl"
            tracer = JsonlTracer(path)
            tracer.emit("tool", tool="https://example.test/run?token=TOP-SECRET-VALUE", status="ok")
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("TOP-SECRET-VALUE", raw)
            data = json.loads(raw)
            self.assertTrue(data["data"]["tool"].startswith("<redacted:sha256:"))

    def test_orchestrator_trace_hashes_task(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trace.jsonl"
            tracer = JsonlTracer(path)
            orchestrator = Orchestrator(
                SkillRegistry.from_file(ROOT / "config/skills/registry.json"),
                ModelRouter.from_file(ROOT / "config/models/catalog.json"),
                PolicyEngine.from_file(ROOT / "config/policies/default.json"),
                tracer,
            )
            secret_task = "Investigate credential SECRET-123"
            orchestrator.plan(secret_task)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn(secret_task, path.read_text(encoding="utf-8"))
            self.assertIn("task_sha256", data["data"])
            self.assertEqual(data["data"]["task_chars"], len(secret_task))
