from __future__ import annotations

import pytest

from aisearcharab_api.generated_answers import (
    EvidenceClaim,
    EvidenceItem,
    GroundedAnswerResponse,
    GroundedCitation,
    TokenUsage,
)
from aisearcharab_api.grounded_workflow import (
    EvidenceChangedDuringGeneration,
    GroundedContractViolation,
    GroundedNoEvidenceError,
    execute_grounded_workflow,
    validate_grounded_contract,
)


def _evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            evidence_id="E1",
            title="Reviewed source",
            url="/reviewed/source/",
            source_urls=("https://example.com/source",),
            claims=(
                EvidenceClaim(
                    claim_key="claim-1",
                    text="Reviewed fact.",
                    claim_type="verified-fact",
                    confidence="high",
                ),
            ),
            content_id="content-1",
            content_revision=4,
        )
    ]


def _result(*, request_id: str = "request-1") -> GroundedAnswerResponse:
    result = GroundedAnswerResponse(
        answer="- FACT [high]: Reviewed fact.",
        citations=[
            GroundedCitation(
                evidence_id="E1",
                title="Reviewed source",
                url="/reviewed/source/",
                source_urls=["https://example.com/source"],
            )
        ],
        uncertainty="low",
        limitations=["reviewed-only"],
        model="test-model",
        request_id=request_id,
        usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    result._selected_claim_refs = (("E1", "claim-1"),)
    return result


def test_contract_accepts_exact_selected_evidence_and_citation() -> None:
    result = _result()
    assert validate_grounded_contract(_evidence(), result, request_id="request-1") is result


def test_contract_rejects_request_id_mismatch() -> None:
    with pytest.raises(GroundedContractViolation, match="request_id mismatch"):
        validate_grounded_contract(_evidence(), _result(), request_id="different")


def test_contract_rejects_citation_not_backed_by_selected_ref() -> None:
    result = _result()
    result.citations = []
    with pytest.raises(GroundedContractViolation, match="citations do not exactly match"):
        validate_grounded_contract(_evidence(), result, request_id="request-1")


def test_contract_rejects_unknown_selected_claim() -> None:
    result = _result()
    result._selected_claim_refs = (("E1", "missing"),)
    with pytest.raises(GroundedContractViolation, match="unknown reviewed claim"):
        validate_grounded_contract(_evidence(), result, request_id="request-1")


def test_insufficient_result_requires_no_claims_or_citations() -> None:
    result = GroundedAnswerResponse(
        answer="The reviewed repository claims available for this query are insufficient to produce a grounded answer.",
        citations=[],
        uncertainty="insufficient",
        limitations=["reviewed-only"],
        model="test-model",
        request_id="request-1",
        usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
    )
    assert validate_grounded_contract(_evidence(), result, request_id="request-1") is result


def test_workflow_executes_governed_order_and_returns_payload_free_traces() -> None:
    calls: list[str] = []
    evidence = _evidence()
    result = _result()

    execution = execute_grounded_workflow(
        request_id="request-1",
        retrieve_step=lambda: calls.append("retrieve") or evidence,
        release_read_transaction_step=lambda: calls.append("release"),
        reserve_quota_step=lambda: calls.append("quota"),
        generate_step=lambda _evidence: calls.append("generate") or result,
        revalidate_step=lambda _evidence, _result: calls.append("revalidate") or True,
    )

    assert calls == ["retrieve", "release", "quota", "generate", "revalidate"]
    assert execution.result is result
    assert [trace.name for trace in execution.traces] == [
        "retrieve_evidence",
        "release_read_transaction",
        "reserve_generation_quota",
        "generate_claim_selection",
        "validate_grounded_contract",
        "revalidate_evidence",
    ]
    assert all(trace.duration_ms >= 0 for trace in execution.traces)


def test_workflow_releases_read_transaction_before_rejecting_empty_evidence() -> None:
    calls: list[str] = []
    with pytest.raises(GroundedNoEvidenceError):
        execute_grounded_workflow(
            request_id="request-1",
            retrieve_step=lambda: calls.append("retrieve") or [],
            release_read_transaction_step=lambda: calls.append("release"),
            reserve_quota_step=lambda: calls.append("quota"),
            generate_step=lambda _evidence: _result(),
            revalidate_step=lambda _evidence, _result: True,
        )
    assert calls == ["retrieve", "release"]


def test_workflow_fails_closed_when_evidence_changes() -> None:
    with pytest.raises(EvidenceChangedDuringGeneration):
        execute_grounded_workflow(
            request_id="request-1",
            retrieve_step=_evidence,
            release_read_transaction_step=lambda: None,
            reserve_quota_step=lambda: None,
            generate_step=lambda _evidence: _result(),
            revalidate_step=lambda _evidence, _result: False,
        )
