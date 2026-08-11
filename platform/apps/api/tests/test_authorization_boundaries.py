from fastapi.testclient import TestClient

from conftest import csrf_from_client


def _login(client: TestClient, credentials: dict[str, str]) -> tuple[dict, dict[str, str]]:
    response = client.post("/v1/auth/login", json=credentials)
    assert response.status_code == 200
    return response.json(), {"X-CSRF-Token": csrf_from_client(client)}


def test_new_editor_can_create_draft_but_cannot_modify_owner(
    client: TestClient,
    owner_credentials: dict[str, str],
) -> None:
    owner_login, owner_headers = _login(client, owner_credentials)
    owner_id = owner_login["user"]["id"]

    step_up = client.post(
        "/v1/auth/step-up",
        headers=owner_headers,
        json={"password": owner_credentials["password"]},
    )
    assert step_up.status_code == 200

    editor_password = "editor-bola-boundary-password-2026"
    created = client.post(
        "/v1/admin/users",
        headers=owner_headers,
        json={
            "email": "boundary-editor@example.com",
            "display_name": "Boundary Editor",
            "role": "editor",
            "password": editor_password,
        },
    )
    assert created.status_code == 201

    logout = client.post("/v1/auth/logout", headers=owner_headers)
    assert logout.status_code == 204

    _, editor_headers = _login(
        client,
        {"email": "boundary-editor@example.com", "password": editor_password},
    )

    draft = client.post(
        "/v1/admin/content",
        headers=editor_headers,
        json={
            "slug": "editor-boundary-draft",
            "url_path": "/reports/editor-boundary-draft/",
            "title": "مسودة اختبار حدود الصلاحيات",
            "summary": "مسودة صحيحة تثبت أن المستخدم الجديد يستطيع تنفيذ رحلته التحريرية المسموح بها.",
            "body": "هذا محتوى اختباري كافٍ لإثبات أن المحرر يستطيع إنشاء مسودة من دون امتلاك صلاحيات إدارة المستخدمين.",
            "section": "reports",
            "language": "ar",
            "source_authority": 5.0,
        },
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"

    bola_attempt = client.patch(
        f"/v1/admin/users/{owner_id}",
        headers=editor_headers,
        json={"display_name": "Compromised Owner Name"},
    )
    assert bola_attempt.status_code == 403
    assert bola_attempt.json()["detail"] == "insufficient permissions"

    owner_read_attempt = client.get("/v1/admin/users")
    assert owner_read_attempt.status_code == 403
