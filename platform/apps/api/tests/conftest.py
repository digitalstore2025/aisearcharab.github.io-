from __future__ import annotations

import json
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aisearcharab_api.config import Settings
from aisearcharab_api.database import Base, get_db
from aisearcharab_api.main import create_app
from aisearcharab_api.models import Claim, ContentItem, Source, User
from aisearcharab_api.security import hash_password

FIXTURES = Path(__file__).parent / "fixtures"
OWNER_EMAIL = "owner@example.com"
OWNER_PASSWORD = "owner-secure-password-2026"


@pytest.fixture()
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    documents = json.loads((FIXTURES / "search_documents.json").read_text(encoding="utf-8"))
    with factory() as session:
        for row in documents:
            published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
            session.add(ContentItem(**{**row, "published_at": published_at, "url_path": f"/{row['section']}/{row['slug']}/"}))
        session.flush()

        item = session.query(ContentItem).filter_by(slug="gpt-5-arabic-analysis").one()
        source = Source(
            source_key="official-model-documentation",
            title="Official model documentation",
            publisher="Official publisher",
            url="https://example.org/official-model-documentation",
            archive_url=None,
            source_type="official-document",
            language="en",
            reliability="primary",
        )
        item.sources.append(source)
        item.claims.append(
            Claim(
                claim_key="retrieval-only-contract",
                text="This API returns ranked documents and does not generate answers.",
                claim_type="verified-fact",
                confidence="high",
                review_status="reviewed",
            )
        )
        session.add(
            User(
                email=OWNER_EMAIL,
                display_name="Platform Owner",
                role="owner",
                password_hash=hash_password(OWNER_PASSWORD),
            )
        )
        session.commit()

    yield factory
    engine.dispose()


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=60,
        login_max_failures=5,
        login_lock_minutes=15,
        password_min_length=14,
    )


@pytest.fixture()
def client(session_factory: sessionmaker[Session], settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def owner_credentials() -> dict[str, str]:
    return {"email": OWNER_EMAIL, "password": OWNER_PASSWORD}


def csrf_from_client(client: TestClient) -> str:
    return client.cookies.get("ais_admin_csrf") or ""
