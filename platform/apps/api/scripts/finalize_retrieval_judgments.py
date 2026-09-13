from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aisearcharab_api.retrieval_judgments import (  # noqa: E402
    finalize_dataset,
    parse_dataset,
    promotion_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate, adjudicate and finalize opaque-ID human retrieval relevance judgments."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--judgments-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--min-queries", type=int, default=100)
    parser.add_argument("--min-kappa", type=float, default=0.60)
    parser.add_argument("--min-annotators", type=int, default=2)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    finalized = finalize_dataset(parse_dataset(payload))

    judgments_payload = {
        "corpus_revision": finalized.corpus_revision,
        "judgments": finalized.judgments,
    }
    evidence_payload = {
        "schema_version": 1,
        "corpus_revision": finalized.corpus_revision,
        "agreement": asdict(finalized.agreement),
        "promotion_thresholds": {
            "min_queries": args.min_queries,
            "min_mean_weighted_kappa": args.min_kappa,
            "min_annotators": args.min_annotators,
        },
        "promotion_gate_passed": promotion_gate(
            finalized,
            min_queries=args.min_queries,
            min_mean_weighted_kappa=args.min_kappa,
            min_annotators=args.min_annotators,
        ),
        "privacy": "outputs contain opaque IDs, relevance grades and aggregate agreement only; no query text",
    }

    args.judgments_output.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    args.judgments_output.write_text(
        json.dumps(judgments_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.evidence_output.write_text(
        json.dumps(evidence_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence_payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if evidence_payload["promotion_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
