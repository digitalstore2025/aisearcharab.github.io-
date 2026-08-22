from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import OpenAI

from aisearcharab_api.generated_answers import (
    EvidenceClaim,
    EvidenceItem,
    UpstreamInvalidResponseError,
    generate_grounded_answer,
)


class FakeResponses:
    def __init__(self, output_text: str, *, usage: object | None) -> None:
        self.output_text = output_text
        self.usage = usage

    def create(self, **_kwargs: Any) -> object:
        return SimpleNamespace(
            status="completed",
            output_text=self.output_text,
            model="gpt-5.6-terra-2026-08-20",
            usage=self.usage,
        )


class FakeOpenAI:
    def __init__(self, output_text: str, *, usage: object | None) -> None:
        self.responses = FakeResponses(output_text, usage=usage)


def _usage() -> object:
    return SimpleNamespace(input_tokens=41, output_tokens=17, total_tokens=58)


def _model_output(claim_keys: list[str], uncertainty: str = "low") -> str:
    return json.dumps({"claim_keys": claim_keys, "uncertainty": uncertainty})


def _generate(
    evidence: list[EvidenceItem],
    claim_keys: list[str],
    *,
    uncertainty: str = "low",
    usage: object | None = None,
):
    fake = FakeOpenAI(
        _model_output(claim_keys, uncertainty),
        usage=_usage() if usage is None else usage,
    )
    return generate_grounded_answer(
        "test query",
        evidence,
        request_id="req-integrity",
        api_key="unused-test-key",
        model="gpt-5.6-terra",
        timeout_seconds=20,
        max_retries=2,
        max_output_tokens=1200,
        client=cast(OpenAI, fake),
    )


def test_server_raises_uncertainty_floor_for_low_confidence_non_fact() -> None:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            title="Reviewed source",
            url="/reviewed-source/",
            claims=(
                EvidenceClaim(
                    claim_key="low-confidence-third-party",
                    text="A reviewed third-party statement.",
                    claim_type="third-party-claim",
                    confidence="low",
                ),
            ),
            source_urls=("https://example.org/source",),
        )
    ]

    result = _generate(evidence, ["low-confidence-third-party"], uncertainty="low")

    assert result.uncertainty == "high"


def test_multi_source_answer_preserves_claim_to_citation_markers() -> None:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            title="First source",
            url="/first/",
            claims=(
                EvidenceClaim(
                    claim_key="claim-one",
                    text="First reviewed fact.",
                    claim_type="verified-fact",
                    confidence="high",
                ),
            ),
            source_urls=("https://example.org/first",),
        ),
        EvidenceItem(
            evidence_id="E2",
            title="Second source",
            url="/second/",
            claims=(
                EvidenceClaim(
                    claim_key="claim-two",
                    text="Second reviewed fact.",
                    claim_type="verified-fact",
                    confidence="high",
                ),
            ),
            source_urls=("https://example.org/second",),
        ),
    ]

    result = _generate(evidence, ["claim-one", "claim-two"])

    assert "[E1:claim-one]" in result.answer
    assert "[E2:claim-two]" in result.answer
    assert [citation.evidence_id for citation in result.citations] == ["E1", "E2"]


@pytest.mark.parametrize(
    ("usage", "message"),
    [
        (None, "omitted token usage provenance"),
        (SimpleNamespace(input_tokens=41, total_tokens=58), "invalid output_tokens provenance"),
    ],
)
def test_missing_provider_usage_fails_closed(usage: object | None, message: str) -> None:
    evidence = [
        EvidenceItem(
            evidence_id="E1",
            title="Reviewed source",
            url="/reviewed-source/",
            claims=(
                EvidenceClaim(
                    claim_key="claim-one",
                    text="First reviewed fact.",
                    claim_type="verified-fact",
                    confidence="high",
                ),
            ),
            source_urls=(),
        )
    ]
    fake = FakeOpenAI(_model_output(["claim-one"]), usage=usage)

    with pytest.raises(UpstreamInvalidResponseError, match=message):
        generate_grounded_answer(
            "test query",
            evidence,
            request_id="req-usage-integrity",
            api_key="unused-test-key",
            model="gpt-5.6-terra",
            timeout_seconds=20,
            max_retries=2,
            max_output_tokens=1200,
            client=cast(OpenAI, fake),
        )
