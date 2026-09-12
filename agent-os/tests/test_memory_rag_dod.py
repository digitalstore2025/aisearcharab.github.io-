import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.dod import code_dod
from agent_os.memory import MemoryItem, MemoryStore
from agent_os.rag import RetrievedChunk, dedupe_and_rank


class TestMemoryRagDoD(unittest.TestCase):
    def test_unverified_memory_not_fact(self):
        store = MemoryStore()
        store.put(MemoryItem("project", "x", "claim", "chat", verified=False))
        self.assertIsNone(store.get("project", "x", require_verified=True))

    def test_rag_dedupes(self):
        chunks = [
            RetrievedChunk("1", "same text", "s", lexical_score=.5, vector_score=.5),
            RetrievedChunk("2", "same   text", "s", lexical_score=.8, vector_score=.8),
        ]
        self.assertEqual(len(dedupe_and_rank(chunks)), 1)
        self.assertEqual(dedupe_and_rank(chunks)[0].id, "2")

    def test_dod_requires_all(self):
        dod = code_dod()
        dod.checks[0].passed = True
        self.assertFalse(dod.complete)
        self.assertIn("targeted_tests_pass", dod.missing())
