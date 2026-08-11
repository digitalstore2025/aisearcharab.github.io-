from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.config import Settings
from aisearcharab_api.database import get_db
from aisearcharab_api.main import create_app
from aisearcharab_api.models import User
from aisearcharab_api.security import hash_password
from conftest import OWNER_EMAIL, OWNER_PASSWORD, csrf_from_client

ADMIN_EMAIL = "governance-admin@example.com"
ADMIN_PASSWORD = "admin-secure-password-2026"
REVIEWER_EMAIL = "reviewer@example.com"
REVIEWER_PASSWORD = "reviewer-secure-password-2026"
PUBLISHER_EMAIL = "publisher@example.com"
PUBLISHER_PASSWORD = "publisher-secure-password-2026"


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"X-CSRF-Token": csrf_from_client(client)}


def _step_up(client: TestClient, password: str, headers: dict[str, str]) -> None:
    response = client.post("/v1/auth/step-up", headers=headers, json={"password": password})
    assert response.status_code == 200


def _logout(client: TestClient, headers: dict[str, str]) -> None:
    assert client.post("/v1/auth/logout", headers=headers).status_code == 204


def test_creator_latest_editor_reviewer_and_publisher_duties_are_separated(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        db.add_all(
            [
                User(
                    email=ADMIN_EMAIL,
                    display_name="Governance Admin",
                    role="admin",
                    password_hash=hash_password(ADMIN_PASSWORD),
                ),
                User(
                    email=REVIEWER_EMAIL,
                    display_name="Independent Reviewer",
                    role="reviewer",
                    password_hash=hash_password(REVIEWER_PASSWORD),
                ),
                User(
                    email=PUBLISHER_EMAIL,
                    display_name="Independent Publisher",
                    role="publisher",
                    password_hash=hash_password(PUBLISHER_PASSWORD),
                ),
            ]
        )
        db.commit()

    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=60,
        session_idle_minutes=30,
        step_up_ttl_minutes=10,
        enforce_separation_of_duties=True,
    )
    app = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        owner_headers = _login(client, OWNER_EMAIL, OWNER_PASSWORD)
        created = client.post(
            "/v1/admin/content",
            headers=owner_headers,
            json={
                "slug": "three-person-governance",
                "url_path": "/reports/three-person-governance/",
                "title": "اختبار فصل واجبات التحرير",
                "summary": "مادة اختبارية للتحقق من فصل المنشئ والمراجع والناشر.",
                "body": "متن اختبار كافٍ للتحقق من أن دورة النشر لا يمكن تنفيذها بهوية واحدة.",
                "section": "reports",
                "language": "ar",
                "source_authority": 8,
            },
        )
        assert created.status_code == 201
        content_id = created.json()["id"]
        source = client.post(
            f"/v1/admin/content/{content_id}/sources",
            headers=owner_headers,
            json={
                "source_key": "three-person-source",
                "title": "Independent primary source",
                "publisher": "Official Publisher",
                "url": "https://example.org/three-person-source",
                "source_type": "official-document",
                "language": "en",
                "reliability": "primary",
            },
        )
        assert source.status_code == 201
        claim = client.post(
            f"/v1/admin/content/{content_id}/claims",
            headers=owner_headers,
            json={
                "claim_key": "three-person-claim",
                "text": "The claim requires an independent reviewer.",
                "claim_type": "verified-fact",
                "confidence": "medium",
            },
        )
        assert claim.status_code == 201
        claim_id = claim.json()["claims"][0]["id"]

        same_creator_review = client.post(
            f"/v1/admin/content/{content_id}/transition",
            headers=owner_headers,
            json={"status": "reviewed"},
        )
        assert same_creator_review.status_code == 409
        _logout(client, owner_headers)

        admin_headers = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        modified = client.patch(
            f"/v1/admin/content/{content_id}",
            headers=admin_headers,
            json={"summary": "تعديل جوهري مستقل يجب ألا يسمح للمحرر نفسه باعتماده للمراجعة."},
        )
        assert modified.status_code == 200
        same_latest_editor_review = client.post(
            f"/v1/admin/content/{content_id}/transition",
            headers=admin_headers,
            json={"status": "reviewed"},
        )
        assert same_latest_editor_review.status_code == 409
        _logout(client, admin_headers)

        reviewer_headers = _login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
        reviewed_claim = client.patch(
            f"/v1/admin/claims/{claim_id}",
            headers=reviewer_headers,
            json={"review_status": "reviewed", "confidence": "high"},
        )
        assert reviewed_claim.status_code == 200
        reviewed_content = client.post(
            f"/v1/admin/content/{content_id}/transition",
            headers=reviewer_headers,
            json={"status": "reviewed"},
        )
        assert reviewed_content.status_code == 200
        _logout(client, reviewer_headers)

        publisher_headers = _login(client, PUBLISHER_EMAIL, PUBLISHER_PASSWORD)
        denied_without_step_up = client.post(
            f"/v1/admin/content/{content_id}/transition",
            headers=publisher_headers,
            json={"status": "published"},
        )
        assert denied_without_step_up.status_code == 403
        assert denied_without_step_up.json()["detail"] == "step-up authentication required"

        _step_up(client, PUBLISHER_PASSWORD, publisher_headers)
        published = client.post(
            f"/v1/admin/content/{content_id}/transition",
            headers=publisher_headers,
            json={"status": "published"},
        )
        assert published.status_code == 200
        assert published.json()["status"] == "published"
        assert published.json()["is_indexed"] is True
