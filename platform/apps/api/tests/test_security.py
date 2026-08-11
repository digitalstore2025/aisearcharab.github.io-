import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient


API_CSP = "default-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def test_security_headers_and_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "request-12345678"})
    assert response.headers["x-request-id"] == "request-12345678"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == API_CSP
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["x-dns-prefetch-control"] == "off"
    assert response.headers["origin-agent-cluster"] == "?1"


def test_admin_csp_rejects_inline_and_object_execution(client: TestClient) -> None:
    response = client.get("/admin/")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "<script>"})
    assert response.headers["x-request-id"] != "<script>"
    assert len(response.headers["x-request-id"]) >= 32


def test_untrusted_host_is_rejected(client: TestClient) -> None:
    response = client.get("/health/live", headers={"Host": "attacker.invalid"})
    assert response.status_code == 400


def test_oversized_declared_body_is_rejected_before_route_handling(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        headers={"Content-Length": "600000", "Content-Type": "application/json"},
        content=b"{}",
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request body too large"


def test_oversized_streamed_body_without_content_length_is_rejected(client: TestClient) -> None:
    def chunks():
        yield b'{"email":"nobody@example.com","password":"'
        yield b"x" * 600_000
        yield b'"}'

    response = client.post(
        "/v1/auth/login",
        headers={"Content-Type": "application/json"},
        content=chunks(),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request body too large"


def test_admin_javascript_has_no_html_execution_sinks() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "aisearcharab_api"
        / "admin_static"
        / "admin.js"
    ).read_text(encoding="utf-8")
    forbidden = (".innerHTML", ".outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function(")
    for sink in forbidden:
        assert sink not in source
    assert ".textContent" in source


def test_unimplemented_upload_surface_rejects_malicious_payload(client: TestClient) -> None:
    malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = client.post(
        "/v1/admin/upload",
        headers={"Content-Type": "image/png"},
        content=malicious_svg,
    )
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == API_CSP


def test_structured_request_log_uses_route_template_and_omits_sensitive_request_data(
    client: TestClient,
    caplog,
) -> None:
    secret_query = "do-not-log-this-query-value"
    with caplog.at_level(logging.INFO, logger="aisearcharab.request"):
        response = client.get(
            f"/v1/content/not-a-real-secret-slug?q={secret_query}",
            headers={
                "X-Request-ID": "structured-log-12345",
                "Authorization": "Bearer do-not-log-token",
                "Cookie": "private_cookie=do-not-log-cookie",
            },
        )
    assert response.status_code == 404

    records = [record for record in caplog.records if record.name == "aisearcharab.request"]
    assert records
    payload = json.loads(records[-1].getMessage())
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "structured-log-12345"
    assert payload["environment"] == "test"
    assert payload["method"] == "GET"
    assert payload["route"] == "/v1/content/{slug}"
    assert payload["status_code"] == 404
    assert payload["duration_ms"] >= 0

    serialized = records[-1].getMessage()
    assert "not-a-real-secret-slug" not in serialized
    assert secret_query not in serialized
    assert "do-not-log-token" not in serialized
    assert "do-not-log-cookie" not in serialized


def test_pre_router_rejection_log_does_not_emit_raw_path(client: TestClient, caplog) -> None:
    raw_path = "/private-looking-path/do-not-log-me"
    with caplog.at_level(logging.INFO, logger="aisearcharab.request"):
        response = client.post(
            raw_path,
            headers={"Content-Length": "600000", "Content-Type": "application/json"},
            content=b"{}",
        )
    assert response.status_code == 413
    records = [record for record in caplog.records if record.name == "aisearcharab.request"]
    assert records
    payload = json.loads(records[-1].getMessage())
    assert payload["route"] == "__unmatched__"
    assert raw_path not in records[-1].getMessage()
