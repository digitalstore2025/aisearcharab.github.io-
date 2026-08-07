from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from aisearcharab_api.config import Settings
from aisearcharab_api.database import get_session_factory
from aisearcharab_api.main import create_app
from aisearcharab_api.mfa import current_counter, totp_code
from aisearcharab_api.models import User
from aisearcharab_api.security import hash_password

PASSWORD = "postgres-mfa-concurrency-password-2026"
MFA_KEY = "postgres-ci-only-mfa-encryption-key-not-secret-2026"


def csrf(client: TestClient) -> str:
    return client.cookies.get("ais_admin_csrf") or ""


def verify(client: TestClient, code: str) -> tuple[int, str]:
    response = client.post(
        "/v1/auth/mfa/verify",
        headers={"X-CSRF-Token": csrf(client)},
        json={"code": code},
    )
    detail = response.json().get("detail", "") if response.headers.get("content-type", "").startswith("application/json") else ""
    return response.status_code, detail


def main() -> None:
    factory = get_session_factory()
    email = f"mfa-concurrency-{uuid4().hex}@example.com"
    with factory() as db:
        db.add(
            User(
                email=email,
                display_name="PostgreSQL MFA Concurrency Probe",
                role="owner",
                password_hash=hash_password(PASSWORD),
            )
        )
        db.commit()

    settings = Settings(
        environment="test",
        database_url=str(factory.kw["bind"].url),
        allowed_origins=("http://testserver",),
        allowed_hosts=("testserver",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=60,
        session_idle_minutes=30,
        require_mfa_for_privileged=True,
        mfa_encryption_key=MFA_KEY,
    )
    settings.validate()
    app = create_app(settings)

    try:
        with TestClient(app) as enrollment_client:
            assert enrollment_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
            headers = {"X-CSRF-Token": csrf(enrollment_client)}
            started = enrollment_client.post(
                "/v1/auth/mfa/enroll/start",
                headers=headers,
                json={"password": PASSWORD},
            )
            assert started.status_code == 200, started.text
            secret = started.json()["secret"]
            initial_code = totp_code(secret, counter=current_counter())
            confirmed = enrollment_client.post(
                "/v1/auth/mfa/enroll/confirm",
                headers=headers,
                json={"code": initial_code},
            )
            assert confirmed.status_code == 200, confirmed.text
            assert enrollment_client.post("/v1/auth/logout", headers=headers).status_code == 204

        client_a = TestClient(app)
        client_b = TestClient(app)
        try:
            assert client_a.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
            assert client_b.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200

            # The next TOTP counter is accepted by the configured +1 skew window. Two
            # simultaneous sessions submit the exact same value; only one may consume it.
            shared_code = totp_code(secret, counter=current_counter() + 1)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda client: verify(client, shared_code), (client_a, client_b)))

            statuses = sorted(status_code for status_code, _detail in results)
            assert statuses == [200, 401], results
            denied = [detail for status_code, detail in results if status_code == 401]
            assert denied == ["invalid authentication code"], results
            print("postgres_mfa_concurrency=pass accepted=1 rejected_replay=1")
        finally:
            client_a.close()
            client_b.close()
    finally:
        with factory() as db:
            db.execute(delete(User).where(User.email == email))
            db.commit()


if __name__ == "__main__":
    main()
