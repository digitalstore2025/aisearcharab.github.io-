from fastapi.testclient import TestClient

from conftest import csrf_from_client


def login_owner(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    response = client.post("/v1/auth/login", json=credentials)
    assert response.status_code == 200
    return {"X-CSRF-Token": csrf_from_client(client)}


def step_up_owner(client: TestClient, credentials: dict[str, str], headers: dict[str, str]) -> None:
    response = client.post("/v1/auth/step-up", headers=headers, json={"password": credentials["password"]})
    assert response.status_code == 200


def create_governance_item(client: TestClient, headers: dict[str, str], slug: str = "arabic-ai-governance") -> dict:
    response = client.post(
        "/v1/admin/content",
        headers=headers,
        json={
            "slug": slug,
            "url_path": f"/reports/{slug}/",
            "title": "حوكمة الذكاء الاصطناعي عربياً",
            "summary": "مادة اختبارية منظمة للتحقق من دورة التحرير والمصادر.",
            "body": "هذا متن اختبار كافٍ للتحقق من إنشاء المادة وتطبيق دورة المراجعة والنشر.",
            "section": "reports",
            "language": "ar",
            "source_authority": 8.0,
        },
    )
    assert response.status_code == 201
    return response.json()


def attach_source(client: TestClient, headers: dict[str, str], content_id: str, source_key: str = "official-governance-source") -> dict:
    response = client.post(
        f"/v1/admin/content/{content_id}/sources",
        headers=headers,
        json={
            "source_key": source_key,
            "title": "Official governance source",
            "publisher": "Official publisher",
            "url": f"https://example.org/{source_key}",
            "source_type": "official-document",
            "language": "en",
            "reliability": "primary",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_governed_content_workflow(client: TestClient, owner_credentials: dict[str, str]) -> None:
    headers = login_owner(client, owner_credentials)
    item = create_governance_item(client, headers)
    content_id = item["id"]
    assert item["status"] == "draft"
    assert item["is_indexed"] is False

    blocked_review = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "reviewed"})
    assert blocked_review.status_code == 409

    attach_source(client, headers, content_id)
    reviewed = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "reviewed"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

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
    assert claimed.json()["status"] == "draft"
    claim_id = claimed.json()["claims"][0]["id"]

    claim_review = client.patch(
        f"/v1/admin/claims/{claim_id}",
        headers=headers,
        json={"review_status": "reviewed", "confidence": "high"},
    )
    assert claim_review.status_code == 200
    assert claim_review.json()["review_status"] == "reviewed"

    reviewed_again = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "reviewed"})
    assert reviewed_again.status_code == 200

    denied_publish = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "published"})
    assert denied_publish.status_code == 403
    assert denied_publish.json()["detail"] == "step-up authentication required"

    step_up_owner(client, owner_credentials, headers)
    published = client.post(f"/v1/admin/content/{content_id}/transition", headers=headers, json={"status": "published"})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["is_indexed"] is True

    search = client.get("/v1/search", params={"q": "حوكمة الذكاء الاصطناعي"})
    assert search.status_code == 200
    assert search.json()["results"][0]["url"] == "/reports/arabic-ai-governance/"

    immutable_update = client.patch(
        f"/v1/admin/content/{content_id}",
        headers=headers,
        json={"title": "عنوان يجب رفضه بعد النشر"},
    )
    assert immutable_update.status_code == 409
    immutable_source = client.post(
        f"/v1/admin/content/{content_id}/sources",
        headers=headers,
        json={
            "source_key": "late-source",
            "title": "Late source",
            "publisher": "Publisher",
            "url": "https://example.org/late-source",
            "source_type": "official-document",
            "language": "en",
            "reliability": "primary",
        },
    )
    assert immutable_source.status_code == 409
    immutable_claim_review = client.patch(
        f"/v1/admin/claims/{claim_id}",
        headers=headers,
        json={"review_status": "rejected", "confidence": "low"},
    )
    assert immutable_claim_review.status_code == 409


def test_editing_reviewed_content_invalidates_review(client: TestClient, owner_credentials: dict[str, str]) -> None:
    headers = login_owner(client, owner_credentials)
    item = create_governance_item(client, headers, slug="review-invalidation")
    attach_source(client, headers, item["id"], source_key="review-invalidation-source")
    reviewed = client.post(f"/v1/admin/content/{item['id']}/transition", headers=headers, json={"status": "reviewed"})
    assert reviewed.status_code == 200

    updated = client.patch(
        f"/v1/admin/content/{item['id']}",
        headers=headers,
        json={"summary": "تعديل جوهري يجب أن يعيد المادة إلى المسودة لإجراء مراجعة جديدة."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "draft"
    assert updated.json()["is_indexed"] is False


def test_owner_can_create_user_editor_cannot_manage_users_and_audit_ids_exist(client: TestClient, owner_credentials: dict[str, str]) -> None:
    headers = login_owner(client, owner_credentials)
    content = create_governance_item(client, headers, slug="audit-target-check")

    denied_without_step_up = client.post(
        "/v1/admin/users",
        headers=headers,
        json={
            "email": "editor@example.com",
            "display_name": "Arabic Editor",
            "role": "editor",
            "password": "editor-secure-password-2026",
        },
    )
    assert denied_without_step_up.status_code == 403
    assert denied_without_step_up.json()["detail"] == "step-up authentication required"

    step_up_owner(client, owner_credentials, headers)
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

    audit = client.get("/v1/admin/audit")
    assert audit.status_code == 200
    create_events = [event for event in audit.json() if event["action"] in {"content.create", "user.create"}]
    assert any(event["action"] == "content.create" and event["target_id"] == content["id"] for event in create_events)
    assert any(event["action"] == "user.create" and event["target_id"] == created.json()["id"] for event in create_events)

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
