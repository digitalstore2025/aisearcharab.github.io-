from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.generated_answers import (
    GroundedAnswerResponse,
    TokenUsage,
    retrieve_evidence,
    revalidate_selected_evidence,
)
from aisearcharab_api.models import ContentItem
from aisearcharab_api.repository import list_indexed_content


def _selection_result(evidence_id: str, claim_key: str) -> GroundedAnswerResponse:
    result = GroundedAnswerResponse(
        answer="reviewed claim",
        citations=[],
        uncertainty="low",
        limitations=[],
        model="gpt-5.6-terra-2026-08-20",
        request_id="req-freshness",
        usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    result._selected_claim_refs = ((evidence_id, claim_key),)
    return result


def test_selected_evidence_is_revalidated_after_concurrent_archive(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        evidence = retrieve_evidence(
            session,
            "GPT-5",
            candidate_limit=100,
            max_sources=3,
            max_evidence_chars=500,
        )
        assert evidence
        selected = evidence[0]
        claim_key = selected.claims[0].claim_key
        result = _selection_result(selected.evidence_id, claim_key)
        session.rollback()

        assert revalidate_selected_evidence(session, evidence, result) is True
        session.rollback()

        current = session.get(ContentItem, selected.content_id)
        assert current is not None
        current.status = "archived"
        current.is_indexed = False
        session.commit()

        assert revalidate_selected_evidence(session, evidence, result) is False


def test_sqlite_ranks_exact_match_before_recent_weak_matches(
    session_factory: sessionmaker[Session],
) -> None:
    query = "xylophone quantumdelta"
    with session_factory() as session:
        session.add(
            ContentItem(
                slug="old-exact-title-match",
                url_path="/tests/old-exact-title-match/",
                title=query,
                summary="old but exact",
                body="",
                section="tests",
                language="en",
                status="published",
                is_indexed=True,
                source_authority=5.0,
                published_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
            )
        )
        for index in range(6):
            session.add(
                ContentItem(
                    slug=f"recent-weak-match-{index}",
                    url_path=f"/tests/recent-weak-match-{index}/",
                    title=f"recent unrelated item {index}",
                    summary="xylophone only",
                    body="",
                    section="tests",
                    language="en",
                    status="published",
                    is_indexed=True,
                    source_authority=5.0,
                    published_at=datetime(2090, 1, index + 1, tzinfo=timezone.utc),
                )
            )
        session.commit()

        bounded = list_indexed_content(session, query, candidate_limit=1)

    assert [item.slug for item in bounded] == ["old-exact-title-match"]
