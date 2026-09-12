from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from .generated_answers import EvidenceItem, GroundedAnswerResponse
from .orchestration import StepTrace


class GroundedWorkflowError(RuntimeError):
    """Base exception for deterministic grounded-answer workflow failures."""


class GroundedNoEvidenceError(GroundedWorkflowError):
    """Raised when retrieval returns no reviewed evidence."""


class GroundedContractViolation(GroundedWorkflowError):
    """Raised when a server-built grounded result violates local invariants."""


class EvidenceChangedDuringGeneration(GroundedWorkflowError):
    """Raised when reviewed evidence changed before the response could be returned."""


class EvidenceRevalidationUnavailable(GroundedWorkflowError):
    """Raised when the database cannot perform the post-provider revalidation."""


@dataclass(frozen=True, slots=True)
class GroundedWorkflowExecution:
    result: GroundedAnswerResponse
    evidence: tuple[EvidenceItem, ...]
    traces: tuple[StepTrace, ...]

    @property
    def provider_path_latency_ms(self) -> float:
        """Latency from provider generation through deterministic postconditions."""
        included = {
            "generate_claim_selection",
            "validate_grounded_contract",
            "revalidate_evidence",
        }
        return round(sum(trace.duration_ms for trace in self.traces if trace.name in included), 3)


def _run_step(name: str, function: Callable[[], object]) -> tuple[object, StepTrace]:
    started = perf_counter()
    value = function()
    return value, StepTrace(name=name, duration_ms=round((perf_counter() - started) * 1000, 3))


def validate_grounded_contract(
    evidence: list[EvidenceItem] | tuple[EvidenceItem, ...],
    result: GroundedAnswerResponse,
    *,
    request_id: str,
) -> GroundedAnswerResponse:
    """Fail closed if a server-built grounded response violates provenance invariants.

    This evaluator is deliberately deterministic. It does not ask another model
    whether an answer is grounded; it verifies identifiers and citations against
    the immutable evidence snapshot that was supplied to the provider.
    """
    if result.request_id != request_id:
        raise GroundedContractViolation("grounded result request_id mismatch")
    if not result.generated:
        raise GroundedContractViolation("grounded endpoint returned a non-generated result")
    if result.retrieval_algorithm != "lexical-v1":
        raise GroundedContractViolation("unexpected retrieval algorithm provenance")
    if not result.answer.strip():
        raise GroundedContractViolation("grounded result answer must not be empty")

    refs = tuple(result._selected_claim_refs)
    citation_ids = [citation.evidence_id for citation in result.citations]
    if len(citation_ids) != len(set(citation_ids)):
        raise GroundedContractViolation("grounded result contains duplicate citations")

    evidence_by_id = {item.evidence_id: item for item in evidence}

    if result.uncertainty == "insufficient":
        if refs or result.citations:
            raise GroundedContractViolation("insufficient result must not contain selected claims or citations")
        return result

    if not refs:
        raise GroundedContractViolation("grounded result must retain selected claim provenance")

    selected_evidence_ids: list[str] = []
    seen_evidence_ids: set[str] = set()
    seen_refs: set[tuple[str, str]] = set()
    for evidence_id, claim_key in refs:
        ref = (evidence_id, claim_key)
        if ref in seen_refs:
            raise GroundedContractViolation("grounded result contains duplicate selected claim provenance")
        seen_refs.add(ref)

        item = evidence_by_id.get(evidence_id)
        if item is None:
            raise GroundedContractViolation("grounded result selected unknown evidence")
        if not any(claim.claim_key == claim_key for claim in item.claims):
            raise GroundedContractViolation("grounded result selected unknown reviewed claim")
        if evidence_id not in seen_evidence_ids:
            seen_evidence_ids.add(evidence_id)
            selected_evidence_ids.append(evidence_id)

    if citation_ids != selected_evidence_ids:
        raise GroundedContractViolation("grounded citations do not exactly match selected evidence provenance")

    return result


def execute_grounded_workflow(
    *,
    request_id: str,
    retrieve_step: Callable[[], list[EvidenceItem]],
    release_read_transaction_step: Callable[[], object],
    reserve_quota_step: Callable[[], object],
    generate_step: Callable[[list[EvidenceItem]], GroundedAnswerResponse],
    revalidate_step: Callable[[list[EvidenceItem], GroundedAnswerResponse], bool],
) -> GroundedWorkflowExecution:
    """Execute the current governed grounded-answer lifecycle in explicit steps.

    The callbacks keep HTTP concerns, SQLAlchemy ownership, quota policy and the
    provider client outside this module. This layer only fixes execution order,
    records payload-free timing traces and enforces deterministic postconditions.
    """
    traces: list[StepTrace] = []

    evidence_value, trace = _run_step("retrieve_evidence", retrieve_step)
    evidence = list(evidence_value)
    traces.append(trace)

    _, trace = _run_step("release_read_transaction", release_read_transaction_step)
    traces.append(trace)
    if not evidence:
        raise GroundedNoEvidenceError("no indexed evidence with approved claims matched the query")

    _, trace = _run_step("reserve_generation_quota", reserve_quota_step)
    traces.append(trace)

    generated_value, trace = _run_step("generate_claim_selection", lambda: generate_step(evidence))
    result = generated_value
    if not isinstance(result, GroundedAnswerResponse):
        raise GroundedContractViolation("generation step returned an unexpected response type")
    traces.append(trace)

    validated_value, trace = _run_step(
        "validate_grounded_contract",
        lambda: validate_grounded_contract(evidence, result, request_id=request_id),
    )
    result = validated_value
    if not isinstance(result, GroundedAnswerResponse):
        raise GroundedContractViolation("contract evaluator returned an unexpected response type")
    traces.append(trace)

    current_value, trace = _run_step("revalidate_evidence", lambda: revalidate_step(evidence, result))
    traces.append(trace)
    if current_value is not True:
        raise EvidenceChangedDuringGeneration("evidence changed during generation")

    return GroundedWorkflowExecution(
        result=result,
        evidence=tuple(evidence),
        traces=tuple(traces),
    )
