from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    queries: int
    mrr_at_10: float
    ndcg_at_10: float
    recall_at_5: float
    precision_at_5: float
    hit_rate_at_10: float
    zero_result_rate: float
    mean_result_count: float


@dataclass(frozen=True, slots=True)
class RetrievalComparison:
    baseline: RetrievalMetrics
    candidate: RetrievalMetrics
    delta_mrr_at_10: float
    delta_ndcg_at_10: float
    delta_recall_at_5: float
    delta_zero_result_rate: float


def _dcg(relevances: Sequence[int], cutoff: int) -> float:
    """Compute graded DCG using exponential gain for relevance grades 0..3."""
    return sum((2.0**rel - 1.0) / math.log2(rank + 2) for rank, rel in enumerate(relevances[:cutoff]))


def _validate_judgments(judgments: Mapping[str, Mapping[str, int]]) -> None:
    if not judgments:
        raise ValueError("judgments must not be empty")
    for query_id, relevance in judgments.items():
        if not query_id.strip():
            raise ValueError("query ids must not be empty")
        if not relevance:
            raise ValueError(f"query {query_id!r} must have at least one judged document")
        for document_id, grade in relevance.items():
            if not document_id.strip():
                raise ValueError(f"query {query_id!r} contains an empty document id")
            if isinstance(grade, bool) or not isinstance(grade, int) or grade < 0 or grade > 3:
                raise ValueError("relevance grades must be integers in the range 0..3")
        if not any(grade > 0 for grade in relevance.values()):
            raise ValueError(f"query {query_id!r} must have at least one relevant document")


def evaluate_rankings(
    *,
    rankings: Mapping[str, Sequence[str]],
    judgments: Mapping[str, Mapping[str, int]],
) -> RetrievalMetrics:
    """Evaluate ranked document identifiers against graded relevance judgments.

    Queries are keyed by opaque query IDs. Query text is intentionally absent from
    this interface so metric reports can be persisted without leaking information
    needs into routine telemetry or CI artifacts.
    """
    _validate_judgments(judgments)
    missing = set(judgments) - set(rankings)
    if missing:
        raise ValueError(f"rankings missing judged queries: {', '.join(sorted(missing))}")

    reciprocal_ranks: list[float] = []
    recalls_at_five: list[float] = []
    precisions_at_five: list[float] = []
    ndcgs_at_ten: list[float] = []
    hits_at_ten = 0
    zero_results = 0
    result_counts: list[int] = []

    for query_id, relevance in judgments.items():
        ranked = list(dict.fromkeys(str(value) for value in rankings[query_id] if str(value)))
        result_counts.append(len(ranked))
        if not ranked:
            zero_results += 1

        relevant = {doc_id for doc_id, grade in relevance.items() if grade > 0}
        first_rank = next((index + 1 for index, doc_id in enumerate(ranked[:10]) if doc_id in relevant), 0)
        reciprocal_ranks.append(0.0 if first_rank == 0 else 1.0 / first_rank)

        top_five = ranked[:5]
        hits_five = sum(1 for doc_id in top_five if doc_id in relevant)
        recalls_at_five.append(hits_five / len(relevant))
        precisions_at_five.append(hits_five / 5.0)

        observed_grades = [relevance.get(doc_id, 0) for doc_id in ranked[:10]]
        ideal_grades = sorted((grade for grade in relevance.values() if grade > 0), reverse=True)[:10]
        ideal_dcg = _dcg(ideal_grades, 10)
        ndcgs_at_ten.append(_dcg(observed_grades, 10) / ideal_dcg if ideal_dcg else 0.0)
        if first_rank:
            hits_at_ten += 1

    total = len(judgments)
    return RetrievalMetrics(
        queries=total,
        mrr_at_10=round(sum(reciprocal_ranks) / total, 4),
        ndcg_at_10=round(sum(ndcgs_at_ten) / total, 4),
        recall_at_5=round(sum(recalls_at_five) / total, 4),
        precision_at_5=round(sum(precisions_at_five) / total, 4),
        hit_rate_at_10=round(hits_at_ten / total, 4),
        zero_result_rate=round(zero_results / total, 4),
        mean_result_count=round(sum(result_counts) / total, 4),
    )


def compare_rankings(
    *,
    baseline_rankings: Mapping[str, Sequence[str]],
    candidate_rankings: Mapping[str, Sequence[str]],
    judgments: Mapping[str, Mapping[str, int]],
) -> RetrievalComparison:
    baseline = evaluate_rankings(rankings=baseline_rankings, judgments=judgments)
    candidate = evaluate_rankings(rankings=candidate_rankings, judgments=judgments)
    return RetrievalComparison(
        baseline=baseline,
        candidate=candidate,
        delta_mrr_at_10=round(candidate.mrr_at_10 - baseline.mrr_at_10, 4),
        delta_ndcg_at_10=round(candidate.ndcg_at_10 - baseline.ndcg_at_10, 4),
        delta_recall_at_5=round(candidate.recall_at_5 - baseline.recall_at_5, 4),
        delta_zero_result_rate=round(candidate.zero_result_rate - baseline.zero_result_rate, 4),
    )


def comparison_passes_gate(
    comparison: RetrievalComparison,
    *,
    min_mrr_delta: float = 0.0,
    min_recall_delta: float = 0.0,
    min_ndcg_delta: float = 0.0,
    max_zero_result_delta: float = 0.0,
) -> bool:
    """Return True only when every configured retrieval quality gate passes."""
    thresholds = (min_mrr_delta, min_recall_delta, min_ndcg_delta, max_zero_result_delta)
    if not all(math.isfinite(value) for value in thresholds):
        raise ValueError("retrieval gate thresholds must be finite")
    return (
        comparison.delta_mrr_at_10 >= min_mrr_delta
        and comparison.delta_recall_at_5 >= min_recall_delta
        and comparison.delta_ndcg_at_10 >= min_ndcg_delta
        and comparison.delta_zero_result_rate <= max_zero_result_delta
    )
