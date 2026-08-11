from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIXTURES = ROOT / "tests" / "fixtures"


def load_documents() -> list[object]:
    from aisearcharab_api.models import ContentItem

    rows = json.loads((FIXTURES / "search_documents.json").read_text(encoding="utf-8"))
    documents: list[object] = []
    for row in rows:
        if row["status"] != "published" or not row["is_indexed"]:
            continue
        published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        documents.append(ContentItem(**{**row, "published_at": published_at}))
    return documents


def _relevant_slugs(case: dict[str, object]) -> list[str]:
    values = case.get("expected_slugs")
    if isinstance(values, list):
        return [str(value) for value in values if str(value)]
    value = case.get("expected_slug")
    return [str(value)] if value else []


def _dcg(binary_relevance: list[int], cutoff: int) -> float:
    return sum(rel / math.log2(rank + 2) for rank, rel in enumerate(binary_relevance[:cutoff]))


def evaluate() -> dict[str, float | int]:
    from aisearcharab_api.search import rank_items

    documents = load_documents()
    queries = json.loads((FIXTURES / "golden_queries.json").read_text(encoding="utf-8"))
    reciprocal_ranks: list[float] = []
    recalls_at_five: list[float] = []
    precisions_at_five: list[float] = []
    ndcgs_at_ten: list[float] = []
    hit_at_ten = 0
    zero_results = 0
    result_counts: list[int] = []

    for case in queries:
        relevant = _relevant_slugs(case)
        if not relevant:
            raise ValueError("every golden query must define expected_slug or expected_slugs")
        relevant_set = set(relevant)
        ranked = rank_items(str(case["query"]), documents)
        slugs = [item.item.slug for item in ranked]
        result_counts.append(len(slugs))
        if not slugs:
            zero_results += 1

        relevant_ranks = [index + 1 for index, slug in enumerate(slugs) if slug in relevant_set]
        first_rank = min(relevant_ranks) if relevant_ranks else 0
        reciprocal_ranks.append(0.0 if first_rank == 0 or first_rank > 10 else 1.0 / first_rank)

        top_five = slugs[:5]
        hits_five = sum(1 for slug in top_five if slug in relevant_set)
        recalls_at_five.append(hits_five / len(relevant_set))
        precisions_at_five.append(hits_five / 5.0)

        top_ten_relevance = [1 if slug in relevant_set else 0 for slug in slugs[:10]]
        ideal_relevance = [1] * min(len(relevant_set), 10)
        ideal_dcg = _dcg(ideal_relevance, 10)
        ndcgs_at_ten.append(_dcg(top_ten_relevance, 10) / ideal_dcg if ideal_dcg else 0.0)
        if any(slug in relevant_set for slug in slugs[:10]):
            hit_at_ten += 1

    total = len(queries)
    if total == 0:
        raise ValueError("golden query fixture must not be empty")
    return {
        "queries": total,
        "documents": len(documents),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "mrr_at_10": round(sum(reciprocal_ranks) / total, 4),
        "ndcg_at_10": round(sum(ndcgs_at_ten) / total, 4),
        "recall_at_5": round(sum(recalls_at_five) / total, 4),
        "precision_at_5": round(sum(precisions_at_five) / total, 4),
        "hit_rate_at_10": round(hit_at_ten / total, 4),
        "zero_result_rate": round(zero_results / total, 4),
        "mean_result_count": round(sum(result_counts) / total, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the transparent lexical search fixture.")
    parser.add_argument("--output", type=Path, help="Optional JSON metrics output path.")
    args = parser.parse_args()

    metrics = evaluate()
    rendered = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    if metrics["mrr_at_10"] < 0.85 or metrics["recall_at_5"] < 1.0 or metrics["zero_result_rate"] > 0.0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
