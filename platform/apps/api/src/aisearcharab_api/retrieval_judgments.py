from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ALLOWED_LOCALES = frozenset({"ar", "en", "tr", "mixed"})


class JudgmentDatasetError(ValueError):
    """Raised when a human-relevance dataset cannot be promoted safely."""


def _opaque_id(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise JudgmentDatasetError(f"{field} must be a string")
    normalized = value.strip()
    if not _ID.fullmatch(normalized):
        raise JudgmentDatasetError(f"{field} must be an opaque identifier using safe characters")
    return normalized


def _grade(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 3:
        raise JudgmentDatasetError(f"{field} must be an integer relevance grade in 0..3")
    return value


@dataclass(frozen=True, slots=True)
class Annotation:
    document_id: str
    annotator_id: str
    grade: int


@dataclass(frozen=True, slots=True)
class Adjudication:
    document_id: str
    adjudicator_id: str
    grade: int


@dataclass(frozen=True, slots=True)
class QueryJudgments:
    query_id: str
    locale: str
    annotations: tuple[Annotation, ...]
    adjudications: tuple[Adjudication, ...]


@dataclass(frozen=True, slots=True)
class HumanJudgmentDataset:
    schema_version: int
    corpus_revision: str
    queries: tuple[QueryJudgments, ...]


@dataclass(frozen=True, slots=True)
class PairAgreement:
    annotator_a: str
    annotator_b: str
    shared_items: int
    exact_agreement: float
    weighted_kappa: float


@dataclass(frozen=True, slots=True)
class AgreementReport:
    query_count: int
    annotation_count: int
    annotator_count: int
    adjudication_count: int
    disagreement_count: int
    unresolved_disagreement_count: int
    pair_agreements: tuple[PairAgreement, ...]
    mean_weighted_kappa: float
    mean_exact_agreement: float


@dataclass(frozen=True, slots=True)
class FinalizedJudgments:
    corpus_revision: str
    judgments: dict[str, dict[str, int]]
    agreement: AgreementReport


def parse_dataset(payload: object) -> HumanJudgmentDataset:
    if not isinstance(payload, dict):
        raise JudgmentDatasetError("dataset must be a JSON object")
    allowed_root = {"schema_version", "corpus_revision", "queries"}
    unknown_root = set(payload) - allowed_root
    if unknown_root:
        raise JudgmentDatasetError(f"dataset contains unsupported fields: {', '.join(sorted(unknown_root))}")
    if payload.get("schema_version") != 1:
        raise JudgmentDatasetError("schema_version must equal 1")
    corpus_revision = _opaque_id(payload.get("corpus_revision"), field="corpus_revision")
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise JudgmentDatasetError("queries must be a non-empty array")

    seen_queries: set[str] = set()
    parsed_queries: list[QueryJudgments] = []
    for raw_query in raw_queries:
        if not isinstance(raw_query, dict):
            raise JudgmentDatasetError("each query entry must be an object")
        allowed_query = {"query_id", "locale", "annotations", "adjudications"}
        unknown_query = set(raw_query) - allowed_query
        if unknown_query:
            raise JudgmentDatasetError(
                "query entries may not contain query text or unsupported fields: " + ", ".join(sorted(unknown_query))
            )
        query_id = _opaque_id(raw_query.get("query_id"), field="query_id")
        if query_id in seen_queries:
            raise JudgmentDatasetError(f"duplicate query_id: {query_id}")
        seen_queries.add(query_id)
        locale = str(raw_query.get("locale", "")).strip().lower()
        if locale not in _ALLOWED_LOCALES:
            raise JudgmentDatasetError("locale must be ar, en, tr, or mixed")

        annotations = _parse_annotations(raw_query.get("annotations"), query_id=query_id)
        adjudications = _parse_adjudications(raw_query.get("adjudications", []), query_id=query_id)
        parsed_queries.append(
            QueryJudgments(
                query_id=query_id,
                locale=locale,
                annotations=annotations,
                adjudications=adjudications,
            )
        )

    return HumanJudgmentDataset(
        schema_version=1,
        corpus_revision=corpus_revision,
        queries=tuple(parsed_queries),
    )


def _parse_annotations(value: object, *, query_id: str) -> tuple[Annotation, ...]:
    if not isinstance(value, list) or not value:
        raise JudgmentDatasetError(f"query {query_id} must contain annotations")
    rows: list[Annotation] = []
    seen: set[tuple[str, str]] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"document_id", "annotator_id", "grade"}:
            raise JudgmentDatasetError("annotations must contain exactly document_id, annotator_id, grade")
        document_id = _opaque_id(raw.get("document_id"), field="document_id")
        annotator_id = _opaque_id(raw.get("annotator_id"), field="annotator_id")
        grade = _grade(raw.get("grade"), field="annotation grade")
        key = (document_id, annotator_id)
        if key in seen:
            raise JudgmentDatasetError(f"duplicate annotation for {query_id}/{document_id}/{annotator_id}")
        seen.add(key)
        rows.append(Annotation(document_id=document_id, annotator_id=annotator_id, grade=grade))
    if len({row.annotator_id for row in rows}) < 2:
        raise JudgmentDatasetError(f"query {query_id} requires at least two independent annotators")
    return tuple(rows)


def _parse_adjudications(value: object, *, query_id: str) -> tuple[Adjudication, ...]:
    if not isinstance(value, list):
        raise JudgmentDatasetError("adjudications must be an array")
    rows: list[Adjudication] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"document_id", "adjudicator_id", "grade"}:
            raise JudgmentDatasetError("adjudications must contain exactly document_id, adjudicator_id, grade")
        document_id = _opaque_id(raw.get("document_id"), field="document_id")
        if document_id in seen:
            raise JudgmentDatasetError(f"duplicate adjudication for {query_id}/{document_id}")
        seen.add(document_id)
        rows.append(
            Adjudication(
                document_id=document_id,
                adjudicator_id=_opaque_id(raw.get("adjudicator_id"), field="adjudicator_id"),
                grade=_grade(raw.get("grade"), field="adjudication grade"),
            )
        )
    return tuple(rows)


def finalize_dataset(dataset: HumanJudgmentDataset) -> FinalizedJudgments:
    final: dict[str, dict[str, int]] = {}
    disagreement_count = 0
    unresolved = 0
    all_annotations: list[tuple[str, str, str, int]] = []
    adjudication_count = 0
    annotators: set[str] = set()

    for query in dataset.queries:
        by_document: dict[str, list[Annotation]] = {}
        for row in query.annotations:
            by_document.setdefault(row.document_id, []).append(row)
            annotators.add(row.annotator_id)
            all_annotations.append((query.query_id, row.document_id, row.annotator_id, row.grade))
        adjudicated = {row.document_id: row for row in query.adjudications}
        adjudication_count += len(query.adjudications)
        unknown_adjudications = set(adjudicated) - set(by_document)
        if unknown_adjudications:
            raise JudgmentDatasetError(
                f"query {query.query_id} adjudicates unannotated documents: {', '.join(sorted(unknown_adjudications))}"
            )

        query_final: dict[str, int] = {}
        for document_id, rows in by_document.items():
            if len({row.annotator_id for row in rows}) < 2:
                raise JudgmentDatasetError(
                    f"query {query.query_id} document {document_id} requires at least two independent judgments"
                )
            grades = {row.grade for row in rows}
            if len(grades) == 1:
                query_final[document_id] = next(iter(grades))
                if document_id in adjudicated and adjudicated[document_id].grade != query_final[document_id]:
                    raise JudgmentDatasetError(
                        f"query {query.query_id} has an adjudication contradicting unanimous annotations"
                    )
            else:
                disagreement_count += 1
                decision = adjudicated.get(document_id)
                if decision is None:
                    unresolved += 1
                    continue
                if decision.adjudicator_id in {row.annotator_id for row in rows}:
                    raise JudgmentDatasetError(
                        f"query {query.query_id} document {document_id} requires an independent adjudicator"
                    )
                query_final[document_id] = decision.grade

        if not any(grade > 0 for grade in query_final.values()):
            raise JudgmentDatasetError(
                f"query {query.query_id} has no finalized positively relevant document"
            )
        final[query.query_id] = query_final

    agreement = _agreement_report(
        dataset=dataset,
        annotations=all_annotations,
        annotators=annotators,
        adjudication_count=adjudication_count,
        disagreement_count=disagreement_count,
        unresolved=unresolved,
    )
    if unresolved:
        raise JudgmentDatasetError(f"dataset contains {unresolved} unresolved annotation disagreements")
    return FinalizedJudgments(
        corpus_revision=dataset.corpus_revision,
        judgments=final,
        agreement=agreement,
    )


def _agreement_report(
    *,
    dataset: HumanJudgmentDataset,
    annotations: Sequence[tuple[str, str, str, int]],
    annotators: set[str],
    adjudication_count: int,
    disagreement_count: int,
    unresolved: int,
) -> AgreementReport:
    by_annotator: dict[str, dict[tuple[str, str], int]] = {}
    for query_id, document_id, annotator_id, grade in annotations:
        by_annotator.setdefault(annotator_id, {})[(query_id, document_id)] = grade

    pairs: list[PairAgreement] = []
    for annotator_a, annotator_b in itertools.combinations(sorted(by_annotator), 2):
        shared = sorted(set(by_annotator[annotator_a]) & set(by_annotator[annotator_b]))
        if not shared:
            continue
        values_a = [by_annotator[annotator_a][item] for item in shared]
        values_b = [by_annotator[annotator_b][item] for item in shared]
        exact = sum(int(a == b) for a, b in zip(values_a, values_b, strict=True)) / len(shared)
        pairs.append(
            PairAgreement(
                annotator_a=annotator_a,
                annotator_b=annotator_b,
                shared_items=len(shared),
                exact_agreement=round(exact, 4),
                weighted_kappa=round(_linear_weighted_kappa(values_a, values_b), 4),
            )
        )
    if not pairs:
        raise JudgmentDatasetError("dataset has no overlapping judgments between independent annotators")

    return AgreementReport(
        query_count=len(dataset.queries),
        annotation_count=len(annotations),
        annotator_count=len(annotators),
        adjudication_count=adjudication_count,
        disagreement_count=disagreement_count,
        unresolved_disagreement_count=unresolved,
        pair_agreements=tuple(pairs),
        mean_weighted_kappa=round(sum(pair.weighted_kappa for pair in pairs) / len(pairs), 4),
        mean_exact_agreement=round(sum(pair.exact_agreement for pair in pairs) / len(pairs), 4),
    )


def _linear_weighted_kappa(values_a: Sequence[int], values_b: Sequence[int]) -> float:
    if len(values_a) != len(values_b) or not values_a:
        raise JudgmentDatasetError("weighted kappa requires equal non-empty rating arrays")
    categories = range(4)
    observed = [[0.0 for _ in categories] for _ in categories]
    counts_a = [0.0 for _ in categories]
    counts_b = [0.0 for _ in categories]
    total = float(len(values_a))
    for a, b in zip(values_a, values_b, strict=True):
        observed[a][b] += 1.0 / total
        counts_a[a] += 1.0 / total
        counts_b[b] += 1.0 / total

    observed_disagreement = 0.0
    expected_disagreement = 0.0
    for a in categories:
        for b in categories:
            weight = abs(a - b) / 3.0
            observed_disagreement += weight * observed[a][b]
            expected_disagreement += weight * counts_a[a] * counts_b[b]
    if math.isclose(expected_disagreement, 0.0):
        return 1.0 if math.isclose(observed_disagreement, 0.0) else 0.0
    return 1.0 - (observed_disagreement / expected_disagreement)


def promotion_gate(
    finalized: FinalizedJudgments,
    *,
    min_queries: int = 100,
    min_mean_weighted_kappa: float = 0.6,
    min_annotators: int = 2,
) -> bool:
    report = finalized.agreement
    return (
        report.query_count >= min_queries
        and report.annotator_count >= min_annotators
        and report.unresolved_disagreement_count == 0
        and report.mean_weighted_kappa >= min_mean_weighted_kappa
    )
