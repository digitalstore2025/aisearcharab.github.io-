from __future__ import annotations

import sqlite3
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .arabic import tokenize
from .config import get_settings


class Base(DeclarativeBase):
    pass


def _sqlite_has_token_match(value: str | None, query: str | None) -> int:
    """Return 1 when the normalized token sets intersect, else 0.

    This keeps SQLite development/test candidate selection aligned with the
    Python lexical ranker without materializing the full indexed corpus in the
    application process. Production PostgreSQL continues to use native FTS.
    """
    query_tokens = set(tokenize(query or ""))
    if not query_tokens:
        return 0
    return int(bool(query_tokens & set(tokenize(value or ""))))


@event.listens_for(Engine, "connect")
def _register_sqlite_functions(dbapi_connection: object, _connection_record: object) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("ais_has_token_match", 2, _sqlite_has_token_match)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
