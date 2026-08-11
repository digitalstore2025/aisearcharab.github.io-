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
    )
    with pytest.raises(ConfigurationError):
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
    )
    with pytest.raises(ConfigurationError):
        settings.validate()
