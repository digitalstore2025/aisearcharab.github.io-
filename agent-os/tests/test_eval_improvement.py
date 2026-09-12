import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.ab_eval import RunMetric, summarize, recommend
from agent_os.failure_clustering import classify


class TestImprovement(unittest.TestCase):
    def test_promote_higher_success(self):
        rows = [
            RunMetric("a","1",False,1,1), RunMetric("a","2",True,1,1),
            RunMetric("b","1",True,1,1), RunMetric("b","2",True,1,1),
        ]
        a,b = summarize(rows)
        self.assertEqual(recommend(a,b), "promote:b:higher_success")

    def test_security_regression_rejected(self):
        rows = [RunMetric("a","1",True,1,1), RunMetric("b","1",True,1,1,security_violations=1)]
        a,b = summarize(rows)
        self.assertIn("security_regression", recommend(a,b))

    def test_failure_classification(self):
        self.assertEqual(classify("The agent stopped early before definition of done"), "completion")
