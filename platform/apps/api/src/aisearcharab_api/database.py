from __future__ import annotations

import sqlite3
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .arabic import normalize_text, protected_entities_in, tokenize
from .config import get_settings


class Base(DeclarativeBase):
    pass


def _token_hit_count(query_tokens: tuple[str, ...], value: str) -> int:
    field_tokens = set(tokenize(value))
    return sum(1 for token in query_tokens if token in field_tokens)


def _sqlite_lexical_score(
    title: str | None,
    summary: str | None,
    body: str | None,
    section: str | None,
    query: str | None,
) -> float:
    """Return a bounded lexical relevance score for SQLite candidate ordering.

    The weights mirror the non-freshness portion of the Python ranker closely
    enough to ensure strong matches are selected before candidate_limit. This is
    a local/test compatibility path; production PostgreSQL continues to use FTS.
    """
    query_value = query or ""
    normalized_query = normalize_text(query_value)
    query_tokens = tuple(dict.fromkeys(tokenize(query_value)))
    if not normalized_query or not query_tokens:
        return 0.0

    normalized_title = normalize_text(title or "")
    normalized_summary = normalize_text(summary or "")
    normalized_body = normalize_text(body or "")
    normalized_section = normalize_text(section or "")

    score = 0.0
    if normalized_query == normalized_title:
        score += 140.0
    elif len(query_tokens) > 1 and normalized_query in normalized_title:
        score += 90.0

    score += _token_hit_count(query_tokens, normalized_title) * 22.0
    score += _token_hit_count(query_tokens, normalized_summary) * 9.0
    score += _token_hit_count(query_tokens, normalized_body) * 2.5
    score += _token_hit_count(query_tokens, normalized_section) * 5.0

    if len(query_tokens) > 1 and normalized_query in normalized_summary:
        score += 25.0
    if len(query_tokens) > 1 and normalized_query in normalized_body:
        score += 8.0

    all_tokens = (
        set(tokenize(normalized_title))
        | set(tokenize(normalized_summary))
        | set(tokenize(normalized_body))
        | set(tokenize(normalized_section))
    )
    if len(query_tokens) > 1 and set(query_tokens).issubset(all_tokens):
        score += 12.0

    for entity in protected_entities_in(query_value):
        if entity in normalized_title:
            score += 60.0
        elif entity in normalized_summary:
            score += 28.0
        elif entity in normalized_body:
            score += 12.0

    return score


@event.listens_for(Engine, "connect")
def _register_sqlite_functions(dbapi_connection: object, _connection_record: object) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("ais_lexical_score", 5, _sqlite_lexical_score)


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
