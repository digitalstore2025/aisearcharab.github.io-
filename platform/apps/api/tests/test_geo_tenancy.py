from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.geo.models import OrganizationMembership
from aisearcharab_api.models import User
from aisearcharab_api.security import hash_password
from conftest import csrf_from_client


SECOND_EMAIL = "tenant-analyst@example.com"
SECOND_PASSWORD = "tenant-analyst-password-2026"


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": csrf_from_client(client)}


def _logout(client: TestClient, headers: dict[str, str]) -> None:
    assert client.post("/v1/auth/logout", headers=headers).status_code == 204


def _add_second_user(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as db:
        user = User(
            email=SECOND_EMAIL,
            display_name="Tenant Analyst",
            role="analyst",
            password_hash=hash_password(SECOND_PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def test_organization_creation_bootstraps_owner_and_project(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    headers = _login(client, owner_credentials["email"], owner_credentials["password"])
    created = client.post(
        "/v1/geo/organizations",
        headers=headers,
        json={"slug": "arabic-geo", "name": "Arabic GEO"},
    )
    assert created.status_code == 201
    organization_id = created.json()["id"]

    project = client.post(
        f"/v1/geo/organizations/{organization_id}/projects",
        headers=headers,
        json={"slug": "main-site", "name": "Main Site", "domain": "EXAMPLE.COM."},
    )
    assert project.status_code == 201
    assert project.json()["organization_id"] == organization_id
    assert project.json()["domain"] == "example.com"

    with session_factory() as db:
        membership = db.query(OrganizationMembership).filter_by(organization_id=organization_id).one()
        assert membership.role == "owner"


def test_cross_tenant_project_list_is_hidden_with_404(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    headers = _login(client, owner_credentials["email"], owner_credentials["password"])
    organization = client.post(
        "/v1/geo/organizations",
        headers=headers,
        json={"slug": "private-org", "name": "Private Organization"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]
    _logout(client, headers)

    _add_second_user(session_factory)
    _login(client, SECOND_EMAIL, SECOND_PASSWORD)
    denied = client.get(f"/v1/geo/organizations/{organization_id}/projects")
    assert denied.status_code == 404
    assert denied.json()["detail"] == "organization not found"


def test_viewer_cannot_create_project(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    headers = _login(client, owner_credentials["email"], owner_credentials["password"])
    organization = client.post(
        "/v1/geo/organizations",
        headers=headers,
        json={"slug": "viewer-org", "name": "Viewer Organization"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]
    _logout(client, headers)

    second_user_id = _add_second_user(session_factory)
    with session_factory() as db:
        db.add(OrganizationMembership(organization_id=organization_id, user_id=second_user_id, role="viewer"))
        db.commit()

    viewer_headers = _login(client, SECOND_EMAIL, SECOND_PASSWORD)
    readable = client.get(f"/v1/geo/organizations/{organization_id}/projects")
    assert readable.status_code == 200

    denied = client.post(
        f"/v1/geo/organizations/{organization_id}/projects",
        headers=viewer_headers,
        json={"slug": "blocked", "name": "Blocked", "domain": "blocked.example"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "insufficient organization permissions"


def test_project_domain_rejects_urls_and_credentials(
    client: TestClient,
    owner_credentials: dict[str, str],
) -> None:
    headers = _login(client, owner_credentials["email"], owner_credentials["password"])
    organization = client.post(
        "/v1/geo/organizations",
        headers=headers,
        json={"slug": "validation-org", "name": "Validation Organization"},
    )
    organization_id = organization.json()["id"]

    for unsafe in ("https://example.com/path", "user@example.com", "example.com:443"):
        response = client.post(
            f"/v1/geo/organizations/{organization_id}/projects",
            headers=headers,
            json={"slug": "unsafe-domain", "name": "Unsafe", "domain": unsafe},
        )
        assert response.status_code == 422
