from fastapi.testclient import TestClient


def test_content_detail_includes_provenance(client: TestClient) -> None:
    response = client.get("/v1/content/gpt-5-arabic-analysis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["source_key"] == "official-model-documentation"
    assert payload["claims"][0]["claim_key"] == "retrieval-only-contract"


def test_draft_content_is_hidden(client: TestClient) -> None:
    response = client.get("/v1/content/draft-hidden-item")
    assert response.status_code == 404
