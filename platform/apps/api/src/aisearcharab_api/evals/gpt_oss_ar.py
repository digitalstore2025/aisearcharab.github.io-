from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_ABSTENTION_MARKERS = (
    "المعلومات غير كافية",
    "لا تتوفر معلومات كافية",
    "لا توجد معلومات كافية",
    "غير مذكور في السياق",
    "لا يذكر السياق",
    "لا يمكن تحديد",
    "لا يمكنني تحديد",
    "لا أستطيع تحديد",
)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).replace("\u0640", "")
    text = _ARABIC_DIACRITICS_RE.sub("", text)
    text = (
        text.replace("\u0622", "\u0627")
        .replace("\u0623", "\u0627")
        .replace("\u0625", "\u0627")
        .replace("\u0649", "\u064a")
    )
    return " ".join(text.casefold().split())


def arabic_letter_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(1 for char in letters if "\u0600" <= char <= "\u06ff")
    return arabic / len(letters)


def extract_urls(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).rstrip(".,،؛;)") for match in _URL_RE.finditer(value))


def _as_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _as_string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    rendered = tuple(_as_string(item, field=field) for item in value)
    if len(set(rendered)) != len(rendered):
        raise ValueError(f"{field} must not contain duplicates")
    return rendered


def _as_term_groups(value: object) -> tuple[tuple[str, ...], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("required_term_groups must be a list")
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(value):
        if not isinstance(group, list) or not group:
            raise ValueError(f"required_term_groups[{index}] must be a non-empty list")
        rendered = tuple(_as_string(item, field=f"required_term_groups[{index}]") for item in group)
        groups.append(rendered)
    return tuple(groups)


@dataclass(frozen=True, slots=True)
class ArabicBenchmarkCase:
    case_id: str
    category: str
    context: str
    question: str
    reference_answer: str
    required_term_groups: tuple[tuple[str, ...], ...] = ()
    required_entities: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    must_abstain: bool = False
    allow_urls: bool = False
    min_arabic_ratio: float = 0.65
    pass_score: float = 0.80

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ArabicBenchmarkCase":
        must_abstain = raw.get("must_abstain", False)
        allow_urls = raw.get("allow_urls", False)
        if not isinstance(must_abstain, bool):
            raise ValueError("must_abstain must be boolean")
        if not isinstance(allow_urls, bool):
            raise ValueError("allow_urls must be boolean")

        min_arabic_ratio = raw.get("min_arabic_ratio", 0.65)
        pass_score = raw.get("pass_score", 0.80)
        if not isinstance(min_arabic_ratio, (int, float)) or isinstance(min_arabic_ratio, bool):
            raise ValueError("min_arabic_ratio must be numeric")
        if not isinstance(pass_score, (int, float)) or isinstance(pass_score, bool):
            raise ValueError("pass_score must be numeric")
        if not 0 <= float(min_arabic_ratio) <= 1:
            raise ValueError("min_arabic_ratio must be between 0 and 1")
        if not 0 <= float(pass_score) <= 1:
            raise ValueError("pass_score must be between 0 and 1")

        case = cls(
            case_id=_as_string(raw.get("id"), field="id"),
            category=_as_string(raw.get("category"), field="category"),
            context=_as_string(raw.get("context"), field="context"),
            question=_as_string(raw.get("question"), field="question"),
            reference_answer=_as_string(raw.get("reference_answer"), field="reference_answer"),
            required_term_groups=_as_term_groups(raw.get("required_term_groups")),
            required_entities=_as_string_tuple(raw.get("required_entities"), field="required_entities"),
            forbidden_terms=_as_string_tuple(raw.get("forbidden_terms"), field="forbidden_terms"),
            must_abstain=must_abstain,
            allow_urls=allow_urls,
            min_arabic_ratio=float(min_arabic_ratio),
            pass_score=float(pass_score),
        )
        if not case.must_abstain and not case.required_term_groups:
            raise ValueError(f"{case.case_id}: grounded cases must define required_term_groups")
        return case


@dataclass(frozen=True, slots=True)
class ArabicCaseScore:
    case_id: str
    category: str
    score: float
    passed: bool
    term_coverage: float
    entity_recall: float
    arabic_ratio: float
    arabic_ok: bool
    abstained: bool
    citation_safe: bool
    forbidden_hits: tuple[str, ...]
    urls: tuple[str, ...]
    latency_ms: int | None = None
    raw_sha256: str | None = None
    answer_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.case_id,
            "category": self.category,
            "score": self.score,
            "passed": self.passed,
            "term_coverage": self.term_coverage,
            "entity_recall": self.entity_recall,
            "arabic_ratio": self.arabic_ratio,
            "arabic_ok": self.arabic_ok,
            "abstained": self.abstained,
            "citation_safe": self.citation_safe,
            "forbidden_hits": list(self.forbidden_hits),
            "urls": list(self.urls),
            "latency_ms": self.latency_ms,
            "raw_sha256": self.raw_sha256,
            **({"answer_text": self.answer_text} if self.answer_text is not None else {}),
        }


def load_cases(payload: Mapping[str, object]) -> tuple[ArabicBenchmarkCase, ...]:
    if payload.get("schema_version") != 1:
        raise ValueError("benchmark schema_version must be 1")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("benchmark cases must be a non-empty list")
    cases = tuple(ArabicBenchmarkCase.from_mapping(raw) for raw in raw_cases if isinstance(raw, Mapping))
    if len(cases) != len(raw_cases):
        raise ValueError("every benchmark case must be an object")
    identifiers = [case.case_id for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("benchmark case ids must be unique")
    return cases


def build_grounded_prompt(case: ArabicBenchmarkCase) -> str:
    return (
        "أجب بالعربية الفصحى اعتمادًا حصريًا على السياق المرجعي أدناه. "
        "إذا لم يتضمن السياق الإجابة، فقل بوضوح إن المعلومات غير كافية ولا تخمّن. "
        "لا تنشئ روابط أو مراجع أو مصادر غير موجودة في السياق.\n\n"
        f"السياق المرجعي:\n{case.context}\n\n"
        f"السؤال:\n{case.question}"
    )


def _contains_normalized(normalized_answer: str, term: str) -> bool:
    normalized_term = normalize_text(term)
    if not normalized_term:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_term)}(?!\w)"
    return re.search(pattern, normalized_answer) is not None


def _coverage(groups: Sequence[Sequence[str]], normalized_answer: str) -> float:
    if not groups:
        return 1.0
    hits = 0
    for group in groups:
        if any(_contains_normalized(normalized_answer, term) for term in group):
            hits += 1
    return hits / len(groups)


def _weighted_score(parts: Iterable[tuple[float, float]]) -> float:
    items = tuple(parts)
    weight = sum(item_weight for item_weight, _ in items)
    if weight <= 0:
        return 0.0
    return sum(item_weight * value for item_weight, value in items) / weight


def score_answer(
    case: ArabicBenchmarkCase,
    answer_text: str,
    *,
    latency_ms: int | None = None,
    raw_sha256: str | None = None,
    include_answer: bool = False,
) -> ArabicCaseScore:
    if not isinstance(answer_text, str):
        raise ValueError("answer_text must be a string")

    normalized_answer = normalize_text(answer_text)
    term_coverage = _coverage(case.required_term_groups, normalized_answer)
    entity_recall = _coverage(tuple((entity,) for entity in case.required_entities), normalized_answer)
    forbidden_hits = tuple(
        term for term in case.forbidden_terms if _contains_normalized(normalized_answer, term)
    )
    urls = extract_urls(answer_text)
    citation_safe = case.allow_urls or not urls
    ratio = arabic_letter_ratio(answer_text)
    arabic_ok = ratio >= case.min_arabic_ratio
    abstained = any(_contains_normalized(normalized_answer, marker) for marker in _ABSTENTION_MARKERS)
    forbidden_clear = not forbidden_hits

    if case.must_abstain:
        score = _weighted_score(
            (
                (0.55, 1.0 if abstained else 0.0),
                (0.20, 1.0 if arabic_ok else 0.0),
                (0.15, 1.0 if citation_safe else 0.0),
                (0.10, 1.0 if forbidden_clear else 0.0),
            )
        )
        passed = score >= case.pass_score and abstained and citation_safe and forbidden_clear
    else:
        parts: list[tuple[float, float]] = [
            (0.50, term_coverage),
            (0.15, 1.0 if arabic_ok else 0.0),
            (0.10, 1.0 if citation_safe else 0.0),
            (0.05, 1.0 if forbidden_clear else 0.0),
        ]
        if case.required_entities:
            parts.append((0.20, entity_recall))
        score = _weighted_score(parts)
        passed = score >= case.pass_score and citation_safe and forbidden_clear

    return ArabicCaseScore(
        case_id=case.case_id,
        category=case.category,
        score=round(score, 4),
        passed=passed,
        term_coverage=round(term_coverage, 4),
        entity_recall=round(entity_recall, 4),
        arabic_ratio=round(ratio, 4),
        arabic_ok=arabic_ok,
        abstained=abstained,
        citation_safe=citation_safe,
        forbidden_hits=forbidden_hits,
        urls=urls,
        latency_ms=latency_ms,
        raw_sha256=raw_sha256,
        answer_text=answer_text if include_answer else None,
    )


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _percentile_nearest_rank(values: Sequence[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(percentile * len(ordered) + 0.999999)))
    return ordered[rank - 1]


def aggregate_scores(
    cases: Sequence[ArabicBenchmarkCase],
    scores: Sequence[ArabicCaseScore],
) -> dict[str, float | int | None]:
    if not cases or len(cases) != len(scores):
        raise ValueError("cases and scores must be non-empty and have matching lengths")

    by_id = {case.case_id: case for case in cases}
    if set(by_id) != {score.case_id for score in scores}:
        raise ValueError("case ids and score ids must match exactly")

    non_abstention = [score for score in scores if not by_id[score.case_id].must_abstain]
    entity_scores = [score.entity_recall for score in scores if by_id[score.case_id].required_entities]
    abstention_scores = [
        1.0 if score.abstained else 0.0
        for score in scores
        if by_id[score.case_id].must_abstain
    ]
    unsupported_url_cases = sum(
        1 for score in scores if score.urls and not by_id[score.case_id].allow_urls
    )
    forbidden_claim_cases = sum(1 for score in scores if score.forbidden_hits)
    latencies = [score.latency_ms for score in scores if score.latency_ms is not None]

    grounded_term_recall = _mean([score.term_coverage for score in non_abstention])
    entity_recall = _mean(entity_scores)
    abstention_accuracy = _mean(abstention_scores)
    total = len(scores)
    return {
        "cases": total,
        "mean_score": round(sum(score.score for score in scores) / total, 4),
        "pass_rate": round(sum(1 for score in scores if score.passed) / total, 4),
        "arabic_locale_rate": round(sum(1 for score in scores if score.arabic_ok) / total, 4),
        "grounded_term_recall": (
            round(grounded_term_recall, 4) if grounded_term_recall is not None else None
        ),
        "entity_recall": round(entity_recall, 4) if entity_recall is not None else None,
        "unsupported_url_rate": round(unsupported_url_cases / total, 4),
        "forbidden_claim_rate": round(forbidden_claim_cases / total, 4),
        "abstention_accuracy": (
            round(abstention_accuracy, 4) if abstention_accuracy is not None else None
        ),
        "latency_p50_ms": _percentile_nearest_rank(latencies, 0.50),
        "latency_p95_ms": _percentile_nearest_rank(latencies, 0.95),
    }


DEFAULT_GATES: dict[str, tuple[str, float]] = {
    "mean_score": (">=", 0.80),
    "pass_rate": (">=", 0.80),
    "arabic_locale_rate": (">=", 0.90),
    "grounded_term_recall": (">=", 0.80),
    "entity_recall": (">=", 0.90),
    "unsupported_url_rate": ("<=", 0.0),
    "forbidden_claim_rate": ("<=", 0.0),
    "abstention_accuracy": (">=", 0.80),
}


def gate_failures(
    metrics: Mapping[str, float | int | None],
    gates: Mapping[str, tuple[str, float]] = DEFAULT_GATES,
) -> tuple[str, ...]:
    failures: list[str] = []
    for metric, (operator, threshold) in gates.items():
        if operator not in {">=", "<="}:
            raise ValueError(f"unsupported gate operator for {metric}: {operator!r}")
        value = metrics.get(metric)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            failures.append(f"{metric}: missing numeric metric")
            continue
        passed = value >= threshold if operator == ">=" else value <= threshold
        if not passed:
            failures.append(f"{metric}: {value} {operator} {threshold} failed")
    return tuple(failures)
