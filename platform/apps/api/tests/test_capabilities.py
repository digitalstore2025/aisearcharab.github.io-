from fastapi.testclient import TestClient


def test_capabilities_do_not_claim_unimplemented_features(client: TestClient) -> None:
    response = client.get("/v1/meta/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "api_version": "0.1.0",
        "retrieval_mode": "lexical-v1",
        "generated_answers": False,
        "rag": False,
        "authentication": False,
        "payments": False,
        "crawling": False,
    }
