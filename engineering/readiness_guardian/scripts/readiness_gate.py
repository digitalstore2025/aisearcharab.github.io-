from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from readiness.engine import load_snapshot, parse_gates, summarize


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed AISearch production readiness gate.")
    parser.add_argument("snapshot", nargs="?", default=str(ROOT / "data" / "snapshot.json"), help="Path to readiness snapshot JSON.")
    args = parser.parse_args()
    summary = summarize(parse_gates(load_snapshot(args.snapshot)))
    print(f"Decision: {summary['decision']}")
    print(f"Blocking pass rate: {summary['blocking_gate_pass_rate']:.1%}")
    print(f"Verified pass rate: {summary['verified_pass_rate']:.1%}")
    print(f"Trust completion: {summary['trust_surface_completion']:.1%}")
    print(f"Blocking not PASS: {summary['blocking_not_pass']}")
    return 0 if summary["production_go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
