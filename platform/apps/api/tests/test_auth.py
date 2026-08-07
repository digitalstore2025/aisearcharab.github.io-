from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.models import AdminSession
from conftest import csrf_from_client


def test_owner_login_me_and_logout(client: TestClient, owner_credentials: dict[str, str]) -> None:
    response = client.post("/v1/auth/login", json=owner_credentials)
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "owner"
    assert "users:manage" in response.json()["user"]["permissions"]
    assert client.cookies.get("ais_admin_session")
    assert csrf_from_client(client)

    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == owner_credentials["email"]

    denied = client.post("/v1/auth/logout")
    assert denied.status_code == 403

    logout = client.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf_from_client(client)})
    assert logout.status_code == 204
    assert client.get("/v1/auth/me").status_code == 401


def test_invalid_login_is_generic(client: TestClient) -> None:
    response = client.post("/v1/auth/login", json={"email": "missing@example.com", "password": "wrong-password-value"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_sensitive_user_creation_requires_step_up_and_expiry(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    assert client.post("/v1/auth/login", json=owner_credentials).status_code == 200
    headers = {"X-CSRF-Token": csrf_from_client(client)}
    payload = {
        "email": "step-up-user@example.com",
        "display_name": "Step Up User",
        "role": "editor",
        "password": "editor-secure-password-2026",
    }

    denied = client.post("/v1/admin/users", headers=headers, json=payload)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "step-up authentication required"

    invalid = client.post("/v1/auth/step-up", headers=headers, json={"password": "wrong-password-value"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "invalid credentials"

    elevated = client.post("/v1/auth/step-up", headers=headers, json={"password": owner_credentials["password"]})
    assert elevated.status_code == 200
    elevated_until = datetime.fromisoformat(elevated.json()["elevated_until"])
    assert elevated_until > datetime.now(timezone.utc)

    created = client.post("/v1/admin/users", headers=headers, json=payload)
    assert created.status_code == 201

    with session_factory() as db:
        admin_session = db.query(AdminSession).filter(AdminSession.revoked_at.is_(None)).one()
        admin_session.elevated_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    denied_after_expiry = client.post(
        "/v1/admin/users",
        headers=headers,
        json={**payload, "email": "step-up-expired@example.com"},
    )
    assert denied_after_expiry.status_code == 403
    assert denied_after_expiry.json()["detail"] == "step-up authentication required"


def test_idle_session_is_revoked_server_side(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    assert client.post("/v1/auth/login", json=owner_credentials).status_code == 200
    with session_factory() as db:
        admin_session = db.query(AdminSession).filter(AdminSession.revoked_at.is_(None)).one()
        admin_session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.commit()
    assert client.get("/v1/auth/me").status_code == 401


def test_admin_console_is_same_origin_and_hardened(client: TestClient) -> None:
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "لوحة الإدارة" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
