from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_os.ab_eval import RunMetric, summarize, recommend


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_file", help="CSV columns: variant,case_id,success,latency_s,tool_calls,input_tokens,output_tokens,cost_usd,security_violations")
    p.add_argument("--baseline", required=True, help="Variant name used as the control/baseline")
    p.add_argument("--candidate", required=True, help="Variant name being evaluated for promotion")
    args = p.parse_args()
    if args.baseline == args.candidate:
        p.error("--baseline and --candidate must be different variants")

    rows = []
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(RunMetric(
                variant=r["variant"], case_id=r["case_id"], success=r["success"].lower() in {"1","true","yes"},
                latency_s=float(r["latency_s"]), tool_calls=int(r["tool_calls"]),
                input_tokens=int(r.get("input_tokens") or 0), output_tokens=int(r.get("output_tokens") or 0),
                cost_usd=float(r.get("cost_usd") or 0), security_violations=int(r.get("security_violations") or 0)
            ))
    summaries = summarize(rows)
    print(json.dumps([s.to_dict() for s in summaries], indent=2))
    by_name = {s.variant: s for s in summaries}
    missing = [name for name in (args.baseline, args.candidate) if name not in by_name]
    if missing:
        p.error(f"Unknown variant(s): {', '.join(missing)}")
    print(recommend(by_name[args.baseline], by_name[args.candidate]))

if __name__ == "__main__":
    main()
