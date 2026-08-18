from fastapi.testclient import TestClient

from conftest import csrf_from_client


def _bootstrap(client: TestClient, owner_credentials: dict[str, str]) -> tuple[str, str, dict[str, str]]:
    assert client.post("/v1/auth/login", json=owner_credentials).status_code == 200
    headers = {"X-CSRF-Token": csrf_from_client(client)}
    org = client.post(
        "/v1/geo/organizations",
        headers=headers,
        json={"slug": "geo-lab", "name": "GEO Lab"},
    )
    assert org.status_code == 201
    org_id = org.json()["id"]
    project = client.post(
        f"/v1/geo/organizations/{org_id}/projects",
        headers=headers,
        json={"slug": "primary-site", "name": "Primary Site", "domain": "example.com"},
    )
    assert project.status_code == 201
    return org_id, project.json()["id"], headers


def test_query_set_and_query_roundtrip(client: TestClient, owner_credentials: dict[str, str]) -> None:
    org_id, project_id, headers = _bootstrap(client, owner_credentials)
    created_set = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets",
        headers=headers,
        json={"slug": "brand-queries", "name": "Brand Queries"},
    )
    assert created_set.status_code == 201
    query_set_id = created_set.json()["id"]

    created_query = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets/{query_set_id}/queries",
        headers=headers,
        json={"text": "  ما أفضل منصة ذكاء اصطناعي عربية؟  ", "language": "ar"},
    )
    assert created_query.status_code == 201
    assert created_query.json()["text"] == "ما أفضل منصة ذكاء اصطناعي عربية؟"

    listed = client.get(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets/{query_set_id}/queries"
    )
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [created_query.json()["id"]]


def test_query_language_validation(client: TestClient, owner_credentials: dict[str, str]) -> None:
    org_id, project_id, headers = _bootstrap(client, owner_credentials)
    query_set = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets",
        headers=headers,
        json={"slug": "test-set", "name": "Test Set"},
    )
    query_set_id = query_set.json()["id"]
    denied = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets/{query_set_id}/queries",
        headers=headers,
        json={"text": "test query", "language": "fr"},
    )
    assert denied.status_code == 422
