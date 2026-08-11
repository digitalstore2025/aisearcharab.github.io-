from fastapi.testclient import TestClient


def test_security_headers_and_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "request-12345678"})
    assert response.headers["x-request-id"] == "request-12345678"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "<script>"})
    assert response.headers["x-request-id"] != "<script>"
    assert len(response.headers["x-request-id"]) >= 32
