from fastapi.testclient import TestClient

from conftest import csrf_from_client


def login_owner(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    response = client.post("/v1/auth/login", json=credentials)
    assert response.status_code == 200
    return {"X-CSRF-Token": csrf_from_client(client)}


def test_governed_content_workflow(client: TestClient, owner_credentials: dict[str, str]) -> None:
    headers = login_owner(client, owner_credentials)
    created = client.post(
        "/v1/admin/content",
        headers=headers,
        json={
            "slug": "arabic-ai-governance",
            "url_path": "/reports/arabic-ai-governance/",
            "title": "حوكمة الذكاء الاصطناعي عربياً",
            "summary": "مادة اختبارية منظمة للتحقق من دورة التحرير والمصادر.",
            "body": "هذا متن اختبار كافٍ للتحقق من إنشاء المادة وتطبيق دورة المراجعة والنشر.",
            "section": "reports",
            "language": "ar",
            "source_authority": 8.0,
        },
    )
    assert created.status_code == 201
    item = created.json()
    content_id = item["id"]
    assert item["status"] == "draft"

    reviewed = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "reviewed"})
    assert reviewed.status_code == 200

    blocked = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "published"})
    assert blocked.status_code == 409

    sourced = client.post(
        f"/v1/admin/content/{content_id}/sources",
        headers=headers,
        json={
            "source_key": "official-governance-source",
            "title": "Official governance source",
            "publisher": "Official publisher",
            "url": "https://example.org/governance",
            "source_type": "official-document",
            "language": "en",
            "reliability": "primary",
        },
    )
    assert sourced.status_code == 201

    claimed = client.post(
        f"/v1/admin/content/{content_id}/claims",
        headers=headers,
        json={
            "claim_key": "governance-test-claim",
            "text": "This claim must be reviewed before publication.",
            "claim_type": "verified-fact",
            "confidence": "medium",
        },
    )
    assert claimed.status_code == 201
    claim_id = claimed.json()["claims"][0]["id"]

    blocked_claim = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "published"})
    assert blocked_claim.status_code == 409

    claim_review = client.patch(
        f"/v1/admin/claims/{claim_id}",
        headers=headers,
        json={"review_status": "reviewed", "confidence": "high"},
    )
    assert claim_review.status_code == 200

    published = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "published"})
    assert published.status_code == 200
    assert published.json()["is_indexed"] is True if "is_indexed" in published.json() else True

    search = client.get("/v1/search", params={"q": "حوكمة الذكاء الاصطناعي"})
    assert search.status_code == 200
    assert search.json()["results"][0]["url"] == "/reports/arabic-ai-governance/"


def test_owner_can_create_user_and_editor_cannot_manage_users(client: TestClient, owner_credentials: dict[str, str]) -> None:
    headers = login_owner(client, owner_credentials)
    created = client.post(
        "/v1/admin/users",
        headers=headers,
        json={
            "email": "editor@example.com",
            "display_name": "Arabic Editor",
            "role": "editor",
            "password": "editor-secure-password-2026",
        },
    )
    assert created.status_code == 201

    client.post("/v1/auth/logout", headers=headers)
    editor_login = client.post(
        "/v1/auth/login",
        json={"email": "editor@example.com", "password": "editor-secure-password-2026"},
    )
    assert editor_login.status_code == 200
    editor_headers = {"X-CSRF-Token": csrf_from_client(client)}
    denied = client.post(
        "/v1/admin/users",
        headers=editor_headers,
        json={
            "email": "other@example.com",
            "display_name": "Other User",
            "role": "analyst",
            "password": "another-secure-password-2026",
        },
    )
    assert denied.status_code == 403
