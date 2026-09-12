from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aisearcharab_api.retrieval_eval import compare_rankings, comparison_passes_gate  # noqa: E402


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rankings(path: Path) -> dict[str, list[str]]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("ranking file must be a JSON object keyed by query_id")
    rankings: dict[str, list[str]] = {}
    for query_id, values in payload.items():
        if not isinstance(query_id, str) or not isinstance(values, list):
            raise ValueError("ranking entries must map string query_id values to arrays")
        rankings[query_id] = [str(value) for value in values]
    return rankings


def _load_judgments(path: Path) -> dict[str, dict[str, int]]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("judgment file must be a JSON object keyed by query_id")
    judgments: dict[str, dict[str, int]] = {}
    for query_id, values in payload.items():
        if not isinstance(query_id, str) or not isinstance(values, dict):
            raise ValueError("judgment entries must map string query_id values to objects")
        grades: dict[str, int] = {}
        for document_id, grade in values.items():
            if not isinstance(document_id, str) or isinstance(grade, bool) or not isinstance(grade, int):
                raise ValueError("judgments must map document ids to integer grades")
            grades[document_id] = grade
        judgments[query_id] = grades
    return judgments


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare offline retrieval rankings without changing production search."
    )
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--min-mrr-delta",
        type=float,
        default=0.0,
        help="Minimum allowed MRR@10 delta candidate-baseline.",
    )
    parser.add_argument(
        "--min-recall-delta",
        type=float,
        default=0.0,
        help="Minimum allowed Recall@5 delta candidate-baseline.",
    )
    parser.add_argument(
        "--min-ndcg-delta",
        type=float,
        default=0.0,
        help="Minimum allowed nDCG@10 delta candidate-baseline.",
    )
    parser.add_argument(
        "--max-zero-result-delta",
        type=float,
        default=0.0,
        help="Maximum allowed increase in zero-result rate.",
    )
    args = parser.parse_args()

    comparison = compare_rankings(
        baseline_rankings=_load_rankings(args.baseline),
        candidate_rankings=_load_rankings(args.candidate),
        judgments=_load_judgments(args.judgments),
    )
    rendered = json.dumps(asdict(comparison), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    return 0 if comparison_passes_gate(
        comparison,
        min_mrr_delta=args.min_mrr_delta,
        min_recall_delta=args.min_recall_delta,
        min_ndcg_delta=args.min_ndcg_delta,
        max_zero_result_delta=args.max_zero_result_delta,
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
