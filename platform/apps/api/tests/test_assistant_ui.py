from __future__ import annotations

from fastapi.testclient import TestClient

from aisearcharab_api.config import Settings
from aisearcharab_api.main import create_app


def test_assistant_redirects_to_trailing_slash(client: TestClient) -> None:
    response = client.get("/assistant", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/assistant/"


def test_assistant_shell_and_assets_are_served(client: TestClient) -> None:
    page = client.get("/assistant/")
    assert page.status_code == 200
    assert "المساعد البحثي الموثّق" in page.text
    assert '<script src="assistant.js" defer></script>' in page.text
    assert '<link rel="stylesheet" href="assistant.css">' in page.text
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
    assert 'apiPath("/auth/mfa/status")' in script.text
    assert 'window.location.assign(new URL("../admin/", window.location.href).toString())' in script.text
    assert "new AbortController()" in script.text
    assert "state.sessionEpoch" in script.text
    assert "controller.signal.aborted" in script.text
    assert 'setStatus("تعذر تأكيد تسجيل الخروج.' in script.text


def test_assistant_internal_citations_are_canonical_origin_only(client: TestClient) -> None:
    script = client.get("/assistant/assistant.js")
    assert script.status_code == 200
    assert "function safeCanonicalUrl" in script.text
    assert "parsed.origin === canonical.origin" in script.text
    assert "canonicalOnly: true" in script.text


def test_admin_clients_honor_runtime_api_prefix(client: TestClient) -> None:
    admin_page = client.get("/admin/")
    assert admin_page.status_code == 200
    assert '<link rel="stylesheet" href="admin.css">' in admin_page.text
    assert '<script src="mfa-bridge.js" defer></script>' in admin_page.text
    assert '<script src="admin.js" defer></script>' in admin_page.text

    admin_script = client.get("/admin/admin.js")
    mfa_bridge = client.get("/admin/mfa-bridge.js")
    assert admin_script.status_code == 200
    assert mfa_bridge.status_code == 200
    assert "fetch('../assistant/config.json'" in admin_script.text
    assert "originalFetch('../assistant/config.json'" in mfa_bridge.text
    assert "config.api_prefix" in admin_script.text
    assert "config.api_prefix" in mfa_bridge.text
    assert "`${apiPrefix}${path}`" in admin_script.text
    assert "`${apiPrefix}${path}`" in mfa_bridge.text
    assert "fetch(`/v1${path}`" not in admin_script.text
    assert "originalFetch(`/v1${path}`" not in mfa_bridge.text


def test_assistant_dark_mode_buttons_keep_aa_contrast_tokens(client: TestClient) -> None:
    stylesheet = client.get("/assistant/assistant.css")
    assert stylesheet.status_code == 200
    assert "--button-bg: #176b5b" in stylesheet.text
    assert "--button-hover: #0f5145" in stylesheet.text
    assert "color: var(--button-text)" in stylesheet.text


def test_assistant_config_exposes_runtime_prefix_and_public_origin(client: TestClient) -> None:
    response = client.get("/assistant/config.json")
    assert response.status_code == 200
    assert response.json() == {
        "api_prefix": "/v1",
        "public_site_origin": "https://aisearcharab.com",
    }


def test_assistant_config_honors_non_default_api_prefix() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/api/v2",
        max_search_limit=20,
        log_queries=False,
    )
    app = create_app(settings)
    with TestClient(app) as custom_client:
        response = custom_client.get("/assistant/config.json")
    assert response.status_code == 200
    assert response.json()["api_prefix"] == "/api/v2"


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
