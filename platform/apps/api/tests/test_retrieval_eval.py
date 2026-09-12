from __future__ import annotations

import pytest

from aisearcharab_api.retrieval_eval import compare_rankings, evaluate_rankings


def _judgments() -> dict[str, dict[str, int]]:
    return {
        "q1": {"doc-a": 3, "doc-b": 1, "noise": 0},
        "q2": {"doc-c": 2},
    }


def test_evaluate_rankings_supports_graded_relevance() -> None:
    metrics = evaluate_rankings(
        rankings={
            "q1": ["doc-a", "noise", "doc-b"],
            "q2": ["doc-c"],
        },
        judgments=_judgments(),
    )

    assert metrics.queries == 2
    assert metrics.mrr_at_10 == 1.0
    assert metrics.recall_at_5 == 1.0
    assert metrics.hit_rate_at_10 == 1.0
    assert metrics.zero_result_rate == 0.0
    assert metrics.ndcg_at_10 > 0.9


def test_compare_rankings_reports_candidate_deltas() -> None:
    comparison = compare_rankings(
        baseline_rankings={
            "q1": ["noise", "doc-a", "doc-b"],
            "q2": [],
        },
        candidate_rankings={
            "q1": ["doc-a", "doc-b"],
            "q2": ["doc-c"],
        },
        judgments=_judgments(),
    )

    assert comparison.delta_mrr_at_10 > 0
    assert comparison.delta_ndcg_at_10 > 0
    assert comparison.delta_recall_at_5 > 0
    assert comparison.delta_zero_result_rate < 0


def test_rankings_must_cover_every_judged_query() -> None:
    with pytest.raises(ValueError, match="rankings missing judged queries"):
        evaluate_rankings(rankings={"q1": ["doc-a"]}, judgments=_judgments())


def test_judgments_require_a_positive_relevance_grade() -> None:
    with pytest.raises(ValueError, match="at least one relevant document"):
        evaluate_rankings(
            rankings={"q1": ["doc-a"]},
            judgments={"q1": {"doc-a": 0}},
        )


@pytest.mark.parametrize("grade", [-1, 4, True])
def test_relevance_grades_are_bounded_integers(grade: object) -> None:
    with pytest.raises(ValueError, match="relevance grades"):
        evaluate_rankings(
            rankings={"q1": ["doc-a"]},
            judgments={"q1": {"doc-a": grade}},  # type: ignore[dict-item]
        )


def test_duplicate_ranked_documents_do_not_inflate_metrics() -> None:
    metrics = evaluate_rankings(
        rankings={"q1": ["doc-a", "doc-a", "doc-a"]},
        judgments={"q1": {"doc-a": 3, "doc-b": 1}},
    )
    assert metrics.recall_at_5 == 0.5
    assert metrics.precision_at_5 == 0.2
