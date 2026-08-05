from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aisearcharab_api.models import ContentItem
from aisearcharab_api.search import rank_items

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def load_documents() -> list[ContentItem]:
    rows = json.loads((FIXTURES / "search_documents.json").read_text(encoding="utf-8"))
    documents: list[ContentItem] = []
    for row in rows:
        if row["status"] != "published" or not row["is_indexed"]:
            continue
        published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        documents.append(ContentItem(**{**row, "published_at": published_at}))
    return documents


def evaluate() -> dict[str, float | int]:
    documents = load_documents()
    queries = json.loads((FIXTURES / "golden_queries.json").read_text(encoding="utf-8"))
    reciprocal_ranks: list[float] = []
    recalled_at_five = 0

    for case in queries:
        ranked = rank_items(case["query"], documents)
        slugs = [item.item.slug for item in ranked]
        try:
            rank = slugs.index(case["expected_slug"]) + 1
        except ValueError:
            rank = 0
        reciprocal_ranks.append(0.0 if rank == 0 else 1.0 / rank)
        if 0 < rank <= 5:
            recalled_at_five += 1

    total = len(queries)
    return {
        "queries": total,
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "recall_at_5": round(recalled_at_five / total, 4),
    }


def main() -> int:
    metrics = evaluate()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if metrics["mrr"] < 0.85 or metrics["recall_at_5"] < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
