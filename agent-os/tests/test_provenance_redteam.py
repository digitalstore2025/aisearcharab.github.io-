import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.provenance import Claim, Evidence
from agent_os.redteam import Finding


class TestProvenanceRedteam(unittest.TestCase):
    def test_contested_claim(self):
        c = Claim("x", evidence=[Evidence("a", True), Evidence("b", False)])
        c.recompute()
        self.assertEqual(c.status, "contested")

    def test_finding_requires_evidence(self):
        f = Finding("security", "high", "Issue", "proof", "fix")
        f.validate()
        with self.assertRaises(ValueError):
            Finding("security", "high", "Issue", "", "fix").validate()
