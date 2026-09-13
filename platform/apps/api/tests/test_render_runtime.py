import pytest

from aisearcharab_api.render_runtime import configure_database_url, normalize_postgres_url


def test_render_connection_string_is_bound_to_psycopg3() -> None:
    raw = "postgresql://app:s%40fe-secret@db.internal:5432/app?sslmode=require"
    assert normalize_postgres_url(raw) == (
        "postgresql+psycopg://app:s%40fe-secret@db.internal:5432/app?sslmode=require"
    )


def test_reviewed_sqlalchemy_url_is_preserved() -> None:
    raw = "postgresql+psycopg://app:secret@db.internal/app"
    assert normalize_postgres_url(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "sqlite:///tmp/test.db",
        "mysql://app:secret@db/app",
        "file:///tmp/database",
        "postgresql:///missing-host",
        "postgresql://db.internal/app",
        "postgresql://app@db.internal/app",
    ],
)
def test_render_runtime_rejects_unreviewed_or_incomplete_database_urls(raw: str) -> None:
    with pytest.raises(RuntimeError):
        normalize_postgres_url(raw)


def test_render_database_reference_has_precedence() -> None:
    env = {
        "RENDER_DATABASE_URL": "postgresql://app:secret@render-db/app",
        "DATABASE_URL": "postgresql+psycopg://app:other@wrong-db/app",
    }
    normalized = configure_database_url(env)
    assert normalized == "postgresql+psycopg://app:secret@render-db/app"
    assert env["DATABASE_URL"] == normalized


def test_explicit_empty_render_database_reference_fails_closed() -> None:
    env = {
        "RENDER_DATABASE_URL": "   ",
        "DATABASE_URL": "postgresql+psycopg://app:other@wrong-db/app",
    }
    with pytest.raises(RuntimeError, match="present but empty"):
        configure_database_url(env)


def test_missing_database_url_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        configure_database_url({})
