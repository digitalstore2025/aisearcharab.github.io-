import pytest

from aisearcharab_api.config import ConfigurationError, Settings


def test_production_rejects_sqlite() -> None:
    settings = Settings(
        environment="production",
        database_url="sqlite:///unsafe.db",
        allowed_origins=("https://aisearcharab.com",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        enforce_separation_of_duties=True,
    )
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_wildcard_cors() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("*",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        enforce_separation_of_duties=True,
    )
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_wildcard_hosts() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("https://aisearcharab.com",),
        allowed_hosts=("*",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        enforce_separation_of_duties=True,
    )
    with pytest.raises(ConfigurationError, match="Wildcard hosts"):
        settings.validate()


def test_query_logging_requires_keyed_hash_secret() -> None:
    settings = Settings(
        environment="staging",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("https://staging.aisearcharab.com",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=True,
        query_hash_key="short",
    )
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_rejects_insecure_or_path_cors_origin() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("http://aisearcharab.com/path",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        enforce_separation_of_duties=True,
    )
    with pytest.raises(ConfigurationError):
        settings.validate()


def test_production_requires_separation_of_duties() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://app:secret@db/app",
        allowed_origins=("https://aisearcharab.com",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        enforce_separation_of_duties=False,
    )
    with pytest.raises(ConfigurationError, match="SEPARATION_OF_DUTIES"):
        settings.validate()


def test_idle_timeout_must_be_lower_than_absolute_timeout() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:8000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
        session_ttl_minutes=30,
        session_idle_minutes=30,
    )
    with pytest.raises(ConfigurationError, match="SESSION_IDLE_MINUTES"):
        settings.validate()
