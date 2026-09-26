from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.fault_benchmark import DEFAULT_SEED, run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic Agent OS fault-injection benchmark")
    parser.add_argument("--out", default="/tmp/agent-os-reliability-benchmark.json")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    report = run_benchmark(repeats=args.repeats, seed=args.seed)
    report["provenance"] = {
        "source_sha": os.getenv("GITHUB_SHA", "local"),
        "source_ref": os.getenv("GITHUB_REF", "local"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Fail-closed structural gates. These do not establish production readiness.
    bounded = report["aggregate"]["bounded_recovery"]
    verified = report["aggregate"]["bounded_recovery_with_verifier"]
    retry_only = report["aggregate"]["retry_only"]

    if verified["duplicate_action_rate"] > bounded["duplicate_action_rate"]:
        raise SystemExit("verified recovery unexpectedly increased duplicate actions")
    if verified["duplicate_action_rate"] > retry_only["duplicate_action_rate"]:
        raise SystemExit("verified recovery unexpectedly worse than retry-only duplicate rate")
    if verified["silent_failure_rate"] > retry_only["silent_failure_rate"]:
        raise SystemExit("verified recovery unexpectedly worse than retry-only silent failure rate")

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
