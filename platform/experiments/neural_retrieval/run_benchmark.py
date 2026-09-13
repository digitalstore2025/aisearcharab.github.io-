from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "platform" / "apps" / "api"
sys.path.insert(0, str(API_DIR / "src"))

from aisearcharab_api.models import ContentItem  # noqa: E402
from aisearcharab_api.retrieval_eval import compare_rankings, comparison_passes_gate  # noqa: E402
from aisearcharab_api.search import rank_items  # noqa: E402

FIXTURES = API_DIR / "tests" / "fixtures"
DEFAULT_CHALLENGE = Path(__file__).with_name("challenge_queries.json")


def _load_documents() -> list[ContentItem]:
    rows = json.loads((FIXTURES / "search_documents.json").read_text(encoding="utf-8"))
    documents: list[ContentItem] = []
    for row in rows:
        if row["status"] != "published" or not row["is_indexed"]:
            continue
        published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        documents.append(ContentItem(**{**row, "published_at": published_at}))
    return documents


def _load_queries(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("challenge query file must be a non-empty JSON array")
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("challenge entries must be objects")
        query_id = str(row.get("id", "")).strip()
        query = str(row.get("query", "")).strip()
        expected_slug = str(row.get("expected_slug", "")).strip()
        kind = str(row.get("kind", "unspecified")).strip() or "unspecified"
        if not query_id or query_id in seen:
            raise ValueError("challenge query IDs must be unique and non-empty")
        if not query or not expected_slug:
            raise ValueError(f"challenge query {query_id!r} is missing query or expected_slug")
        seen.add(query_id)
        rows.append({"id": query_id, "query": query, "expected_slug": expected_slug, "kind": kind})
    return rows


def _document_text(item: ContentItem) -> str:
    return "\n".join((item.title, item.summary, item.body, item.section)).strip()


def _lexical_rankings(queries: list[dict[str, str]], documents: list[ContentItem]) -> dict[str, list[str]]:
    return {
        row["id"]: [ranked.item.slug for ranked in rank_items(row["query"], documents)]
        for row in queries
    }


def _dense_rankings(
    *,
    queries: list[dict[str, str]],
    documents: list[ContentItem],
    model_name: str,
    revision: str | None,
    family: str,
    device: str,
    batch_size: int,
    max_seq_length: int,
) -> tuple[dict[str, list[str]], float]:
    from sentence_transformers import SentenceTransformer

    started = time.perf_counter()
    model = SentenceTransformer(
        model_name,
        revision=revision,
        trust_remote_code=False,
        device=device,
    )
    model.max_seq_length = min(int(model.max_seq_length), max_seq_length)

    query_texts = [row["query"] for row in queries]
    document_texts = [_document_text(item) for item in documents]
    if family == "e5":
        query_texts = [f"query: {value}" for value in query_texts]
        document_texts = [f"passage: {value}" for value in document_texts]

    query_embeddings = model.encode(
        query_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    document_embeddings = model.encode(
        document_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    if query_embeddings.ndim != 2 or document_embeddings.ndim != 2:
        raise RuntimeError("embedding model returned an unexpected tensor rank")
    if query_embeddings.shape[1] != document_embeddings.shape[1]:
        raise RuntimeError("query and document embeddings have incompatible dimensions")
    if not np.isfinite(query_embeddings).all() or not np.isfinite(document_embeddings).all():
        raise RuntimeError("embedding model returned non-finite values")

    scores = query_embeddings @ document_embeddings.T
    slugs = [item.slug for item in documents]
    rankings: dict[str, list[str]] = {}
    for index, row in enumerate(queries):
        order = np.argsort(-scores[index], kind="stable")
        rankings[row["id"]] = [slugs[int(position)] for position in order]
    elapsed_ms = (time.perf_counter() - started) * 1000
    return rankings, elapsed_ms


def _judgments(queries: list[dict[str, str]], known_slugs: set[str]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for row in queries:
        if row["expected_slug"] not in known_slugs:
            raise ValueError(f"unknown expected slug for {row['id']}: {row['expected_slug']}")
        output[row["id"]] = {row["expected_slug"]: 3}
    return output


def _top1_accuracy(rankings: dict[str, list[str]], queries: list[dict[str, str]]) -> float:
    hits = 0
    for row in queries:
        values = rankings.get(row["id"], [])
        hits += int(bool(values) and values[0] == row["expected_slug"])
    return round(hits / len(queries), 4)


def _kind_accuracy(rankings: dict[str, list[str]], queries: list[dict[str, str]]) -> dict[str, float]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in queries:
        groups.setdefault(row["kind"], []).append(row)
    return {kind: _top1_accuracy(rankings, rows) for kind, rows in sorted(groups.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline neural retrieval benchmark against AISearch lexical baseline.")
    parser.add_argument("--model", default="intfloat/multilingual-e5-base")
    parser.add_argument("--revision", default="f7d866c89004f9c578631ccaca8bb7b28e7315f2")
    parser.add_argument("--family", choices=("e5", "bge", "generic"), default="e5")
    parser.add_argument("--queries", type=Path, default=DEFAULT_CHALLENGE)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-mrr-delta", type=float, default=0.05)
    parser.add_argument("--min-recall-delta", type=float, default=0.05)
    parser.add_argument("--min-ndcg-delta", type=float, default=0.05)
    parser.add_argument("--max-zero-result-delta", type=float, default=0.0)
    args = parser.parse_args()

    if args.batch_size < 1 or args.batch_size > 128:
        raise ValueError("batch size must be between 1 and 128")
    if args.max_seq_length < 32 or args.max_seq_length > 8192:
        raise ValueError("max sequence length must be between 32 and 8192")

    documents = _load_documents()
    queries = _load_queries(args.queries)
    known_slugs = {item.slug for item in documents}
    judgments = _judgments(queries, known_slugs)

    lexical = _lexical_rankings(queries, documents)
    dense, neural_elapsed_ms = _dense_rankings(
        queries=queries,
        documents=documents,
        model_name=args.model,
        revision=args.revision or None,
        family=args.family,
        device=args.device,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
    )
    comparison = compare_rankings(
        baseline_rankings=lexical,
        candidate_rankings=dense,
        judgments=judgments,
    )

    report = {
        "experiment": "offline-neural-retrieval",
        "model": args.model,
        "revision": args.revision,
        "family": args.family,
        "device": args.device,
        "query_count": len(queries),
        "document_count": len(documents),
        "neural_elapsed_ms": round(neural_elapsed_ms, 3),
        "lexical_top1_accuracy": _top1_accuracy(lexical, queries),
        "candidate_top1_accuracy": _top1_accuracy(dense, queries),
        "lexical_top1_by_kind": _kind_accuracy(lexical, queries),
        "candidate_top1_by_kind": _kind_accuracy(dense, queries),
        "comparison": asdict(comparison),
        "privacy": "report contains opaque query IDs/aggregate metrics only; query text is not emitted",
        "promotion_status": "experiment-only; human-reviewed benchmark and staging evidence still required",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    passed = comparison_passes_gate(
        comparison,
        min_mrr_delta=args.min_mrr_delta,
        min_recall_delta=args.min_recall_delta,
        min_ndcg_delta=args.min_ndcg_delta,
        max_zero_result_delta=args.max_zero_result_delta,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
