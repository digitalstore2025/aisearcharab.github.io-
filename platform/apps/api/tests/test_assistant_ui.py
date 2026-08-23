from __future__ import annotations

from fastapi.testclient import TestClient


def test_assistant_redirects_to_trailing_slash(client: TestClient) -> None:
    response = client.get("/assistant", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/assistant/"


def test_assistant_shell_and_assets_are_served(client: TestClient) -> None:
    page = client.get("/assistant/")
    assert page.status_code == 200
    assert "المساعد البحثي الموثّق" in page.text
    assert '<script src="/assistant/assistant.js" defer></script>' in page.text
    assert '<link rel="stylesheet" href="/assistant/assistant.css">' in page.text
    assert 'minlength="1" maxlength="256"' in page.text
    assert "<script>" not in page.text
    assert "style=" not in page.text

    script = client.get("/assistant/assistant.js")
    stylesheet = client.get("/assistant/assistant.css")
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "text/javascript" in script.headers["content-type"]
    assert "text/css" in stylesheet.headers["content-type"]


def test_assistant_client_bridges_mfa_and_invalidates_stale_answers(client: TestClient) -> None:
    script = client.get("/assistant/assistant.js")
    assert script.status_code == 200
    assert 'api("/v1/auth/mfa/status"' in script.text
    assert 'window.location.assign("/admin/")' in script.text
    assert "new AbortController()" in script.text
    assert "state.sessionEpoch" in script.text
    assert "controller.signal.aborted" in script.text


def test_assistant_uses_strict_self_only_ui_csp(client: TestClient) -> None:
    response = client.get("/assistant/")
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_api_routes_keep_non_document_csp(client: TestClient) -> None:
    response = client.get("/health/live")
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src" not in csp
