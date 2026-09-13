from __future__ import annotations

import pytest

from aisearcharab_api.retrieval_judgments import (
    JudgmentDatasetError,
    finalize_dataset,
    parse_dataset,
    promotion_gate,
)


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "corpus_revision": "corpus-abc123",
        "queries": [
            {
                "query_id": "q-0001",
                "locale": "ar",
                "annotations": [
                    {"document_id": "doc-a", "annotator_id": "r-01", "grade": 3},
                    {"document_id": "doc-a", "annotator_id": "r-02", "grade": 2},
                    {"document_id": "doc-b", "annotator_id": "r-01", "grade": 0},
                    {"document_id": "doc-b", "annotator_id": "r-02", "grade": 0},
                ],
                "adjudications": [
                    {"document_id": "doc-a", "adjudicator_id": "r-03", "grade": 3},
                ],
            },
            {
                "query_id": "q-0002",
                "locale": "mixed",
                "annotations": [
                    {"document_id": "doc-c", "annotator_id": "r-01", "grade": 2},
                    {"document_id": "doc-c", "annotator_id": "r-02", "grade": 2},
                    {"document_id": "doc-d", "annotator_id": "r-01", "grade": 0},
                    {"document_id": "doc-d", "annotator_id": "r-02", "grade": 0},
                ],
                "adjudications": [],
            },
        ],
    }


def test_finalizes_only_after_independent_adjudication() -> None:
    finalized = finalize_dataset(parse_dataset(_payload()))

    assert finalized.corpus_revision == "corpus-abc123"
    assert finalized.judgments == {
        "q-0001": {"doc-a": 3, "doc-b": 0},
        "q-0002": {"doc-c": 2, "doc-d": 0},
    }
    assert finalized.agreement.query_count == 2
    assert finalized.agreement.annotator_count == 2
    assert finalized.agreement.adjudication_count == 1
    assert finalized.agreement.disagreement_count == 1
    assert finalized.agreement.unresolved_disagreement_count == 0
    assert -1.0 <= finalized.agreement.mean_weighted_kappa <= 1.0


def test_query_text_is_rejected_from_ci_dataset_schema() -> None:
    payload = _payload()
    payload["queries"][0]["query_text"] = "هذا النص لا يجب أن يدخل ملف CI"  # type: ignore[index]
    with pytest.raises(JudgmentDatasetError, match="query text"):
        parse_dataset(payload)


def test_disagreement_without_adjudication_fails_closed() -> None:
    payload = _payload()
    payload["queries"][0]["adjudications"] = []  # type: ignore[index]
    with pytest.raises(JudgmentDatasetError, match="unresolved"):
        finalize_dataset(parse_dataset(payload))


def test_adjudicator_must_be_independent_from_original_annotators() -> None:
    payload = _payload()
    payload["queries"][0]["adjudications"][0]["adjudicator_id"] = "r-01"  # type: ignore[index]
    with pytest.raises(JudgmentDatasetError, match="independent adjudicator"):
        finalize_dataset(parse_dataset(payload))


def test_every_document_requires_two_independent_judgments() -> None:
    payload = _payload()
    payload["queries"][0]["annotations"] = [  # type: ignore[index]
        {"document_id": "doc-a", "annotator_id": "r-01", "grade": 3},
        {"document_id": "doc-b", "annotator_id": "r-01", "grade": 0},
        {"document_id": "doc-b", "annotator_id": "r-02", "grade": 0},
    ]
    with pytest.raises(JudgmentDatasetError, match="requires at least two independent judgments"):
        finalize_dataset(parse_dataset(payload))


def test_duplicate_annotation_is_rejected() -> None:
    payload = _payload()
    payload["queries"][0]["annotations"].append(  # type: ignore[index]
        {"document_id": "doc-a", "annotator_id": "r-01", "grade": 3}
    )
    with pytest.raises(JudgmentDatasetError, match="duplicate annotation"):
        parse_dataset(payload)


@pytest.mark.parametrize("grade", [-1, 4, True, 1.5])
def test_relevance_grade_is_strictly_bounded(grade: object) -> None:
    payload = _payload()
    payload["queries"][0]["annotations"][0]["grade"] = grade  # type: ignore[index]
    with pytest.raises(JudgmentDatasetError, match="0..3"):
        parse_dataset(payload)


def test_promotion_gate_requires_scale_and_agreement() -> None:
    finalized = finalize_dataset(parse_dataset(_payload()))
    assert promotion_gate(finalized) is False
    assert promotion_gate(
        finalized,
        min_queries=2,
        min_mean_weighted_kappa=-1.0,
        min_annotators=2,
    ) is True


def test_unanimous_annotation_cannot_be_overridden_by_adjudication() -> None:
    payload = _payload()
    payload["queries"][1]["adjudications"] = [  # type: ignore[index]
        {"document_id": "doc-c", "adjudicator_id": "r-03", "grade": 3}
    ]
    with pytest.raises(JudgmentDatasetError, match="contradicting unanimous"):
        finalize_dataset(parse_dataset(payload))


def test_query_requires_at_least_one_final_positive_document() -> None:
    payload = _payload()
    payload["queries"][1]["annotations"] = [  # type: ignore[index]
        {"document_id": "doc-c", "annotator_id": "r-01", "grade": 0},
        {"document_id": "doc-c", "annotator_id": "r-02", "grade": 0},
    ]
    with pytest.raises(JudgmentDatasetError, match="no finalized positively relevant document"):
        finalize_dataset(parse_dataset(payload))
