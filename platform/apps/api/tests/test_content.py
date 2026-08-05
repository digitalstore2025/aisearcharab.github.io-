from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from aisearcharab_api.models import Claim, ContentItem


def test_content_detail_includes_approved_provenance(client: TestClient) -> None:
    response = client.get("/v1/content/gpt-5-arabic-analysis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["source_key"] == "official-model-documentation"
    assert payload["claims"][0]["claim_key"] == "retrieval-only-contract"
    assert payload["is_indexed"] is True


def test_public_content_hides_draft_and_rejected_claims(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        item = session.query(ContentItem).filter_by(slug="gpt-5-arabic-analysis").one()
        item.claims.extend(
            [
                Claim(
                    claim_key="hidden-draft-claim",
                    text="Draft claims must not be exposed publicly.",
                    claim_type="third-party-claim",
                    confidence="unverified",
                    review_status="draft",
                ),
                Claim(
                    claim_key="hidden-rejected-claim",
                    text="Rejected claims must not be exposed publicly.",
                    claim_type="third-party-claim",
                    confidence="low",
                    review_status="rejected",
                ),
            ]
        )
        session.commit()

    response = client.get("/v1/content/gpt-5-arabic-analysis")
    assert response.status_code == 200
    claim_keys = {claim["claim_key"] for claim in response.json()["claims"]}
    assert claim_keys == {"retrieval-only-contract"}


def test_draft_content_is_hidden(client: TestClient) -> None:
    response = client.get("/v1/content/draft-hidden-item")
    assert response.status_code == 404
