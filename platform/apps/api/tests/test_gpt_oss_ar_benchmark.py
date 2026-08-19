from __future__ import annotations

import json
from pathlib import Path

import pytest

from aisearcharab_api.evals.gpt_oss_ar import (
    aggregate_scores,
    arabic_letter_ratio,
    build_grounded_prompt,
    extract_urls,
    gate_failures,
    load_cases,
    normalize_text,
    score_answer,
)

FIXTURE = Path(__file__).parent / "fixtures" / "gpt_oss_ar_benchmark.json"


def _cases():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return load_cases(payload)


def test_fixture_has_versioned_unique_multidimensional_cases() -> None:
    cases = _cases()
    assert len(cases) >= 10
    assert len({case.case_id for case in cases}) == len(cases)
    categories = {case.category for case in cases}
    assert {"grounding", "arithmetic", "entity", "abstention", "citation_safety", "negation"} <= categories


def test_golden_reference_answers_pass_all_gates() -> None:
    cases = _cases()
    scores = [score_answer(case, case.reference_answer) for case in cases]
    metrics = aggregate_scores(cases, scores)

    assert metrics["pass_rate"] == 1.0
    assert metrics["unsupported_url_rate"] == 0.0
    assert metrics["forbidden_claim_rate"] == 0.0
    assert gate_failures(metrics) == ()


def test_grounded_prompt_keeps_context_and_requires_abstention() -> None:
    case = _cases()[0]
    prompt = build_grounded_prompt(case)

    assert case.context in prompt
    assert case.question in prompt
    assert "اعتمادًا حصريًا" in prompt
    assert "المعلومات غير كافية" in prompt
    assert "لا تنشئ روابط" in prompt


def test_score_rejects_unsupported_url_and_false_claim() -> None:
    case = next(case for case in _cases() if case.case_id == "grounding-platform-owner")
    score = score_answer(
        case,
        "طورت شركة الأفق منصة مسبار في مايو 2025. المصدر: https://example.invalid",
    )

    assert score.passed is False
    assert score.citation_safe is False
    assert score.urls == ("https://example.invalid",)
    assert set(score.forbidden_hits) == {"طورت شركة الأفق", "مايو 2025"}


def test_abstention_requires_explicit_uncertainty() -> None:
    case = next(case for case in _cases() if case.case_id == "abstention-pricing")

    safe = score_answer(case, "المعلومات غير كافية لتحديد السعر لأنه غير مذكور في السياق.")
    invented = score_answer(case, "سعر الاشتراك 100 دولار شهريًا.")

    assert safe.passed is True
    assert safe.abstained is True
    assert invented.passed is False
    assert invented.abstained is False
    assert invented.forbidden_hits == ("100 دولار",)


def test_boundary_aware_matching_rejects_substrings() -> None:
    cases = _cases()
    ranking = next(case for case in cases if case.case_id == "ordered-ranking")
    ranking_score = score_answer(
        ranking,
        "الترتيب: جيم 0.91، ثم المعين 0.82، ثم باء 0.76.",
    )
    assert ranking_score.term_coverage == pytest.approx(2 / 3, abs=0.0001)
    assert ranking_score.entity_recall == pytest.approx(2 / 3, abs=0.0001)

    arithmetic = next(case for case in cases if case.case_id == "arithmetic-total-mentions")
    arithmetic_score = score_answer(arithmetic, "المجموع 150 إجابة للجهة ألف.")
    assert arithmetic_score.term_coverage == 0.0


def test_case_pass_requires_arabic_locale_compliance() -> None:
    case = next(case for case in _cases() if case.case_id == "grounding-platform-owner")
    answer = case.reference_answer + " " + ("English padding words only " * 80)
    score = score_answer(case, answer)

    assert score.term_coverage == 1.0
    assert score.entity_recall == 1.0
    assert score.score >= case.pass_score
    assert score.arabic_ok is False
    assert score.passed is False


def test_aggregate_scores_fails_closed_on_length_and_id_mismatch() -> None:
    cases = _cases()
    first = score_answer(cases[0], cases[0].reference_answer)
    second = score_answer(cases[1], cases[1].reference_answer)

    with pytest.raises(ValueError, match="matching lengths"):
        aggregate_scores(cases[:2], [first])

    with pytest.raises(ValueError, match="ids"):
        aggregate_scores(cases[:1], [second])


def test_undefined_metrics_do_not_look_perfect_and_fail_default_gate() -> None:
    case = next(case for case in _cases() if not case.must_abstain and case.required_entities)
    score = score_answer(case, case.reference_answer)
    metrics = aggregate_scores([case], [score])

    assert metrics["abstention_accuracy"] is None
    failures = gate_failures(metrics)
    assert any(failure.startswith("abstention_accuracy:") for failure in failures)


def test_gate_operator_validation_fails_fast() -> None:
    with pytest.raises(ValueError, match="unsupported gate operator"):
        gate_failures({"example": 1.0}, {"example": ("=>", 0.5)})


def test_arabic_normalization_ratio_and_url_extraction() -> None:
    assert normalize_text("مِسْبَار") == "مسبار"
    assert arabic_letter_ratio("هذه إجابة عربية واضحة.") > 0.95
    assert extract_urls("راجع https://example.com/test، ثم أكمل.") == ("https://example.com/test",)
