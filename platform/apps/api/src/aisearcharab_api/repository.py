from __future__ import annotations

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session, selectinload

from .arabic import normalize_text
from .models import ContentItem

# Keep PostgreSQL candidate selection aligned with the Python Arabic normalizer.
# translate() maps the first seven characters and deletes tatweel/diacritics that
# have no corresponding replacement character.
_POSTGRES_TRANSLATE_FROM = (
    "إأآٱىؤئـ"
    + "".join(chr(codepoint) for codepoint in range(0x0610, 0x061B))
    + "".join(chr(codepoint) for codepoint in range(0x064B, 0x0660))
    + "\u0670"
    + "".join(chr(codepoint) for codepoint in range(0x06D6, 0x06EE))
)
_POSTGRES_TRANSLATE_TO = "اااايوي"
_SIMPLE_REGCONFIG = literal_column("'simple'::regconfig")
_TRANSLATE_FROM_SQL = literal_column("'" + _POSTGRES_TRANSLATE_FROM.replace("'", "''") + "'")
_TRANSLATE_TO_SQL = literal_column("'" + _POSTGRES_TRANSLATE_TO.replace("'", "''") + "'")


def _postgres_search_document():
    combined = (
        func.coalesce(ContentItem.title, "")
        + " "
        + func.coalesce(ContentItem.summary, "")
        + " "
        + func.coalesce(ContentItem.body, "")
        + " "
        + func.coalesce(ContentItem.section, "")
    )
    normalized = func.translate(func.lower(combined), _TRANSLATE_FROM_SQL, _TRANSLATE_TO_SQL)
    return func.to_tsvector(_SIMPLE_REGCONFIG, normalized)


def _postgres_tsquery(query: str):
    return func.websearch_to_tsquery(_SIMPLE_REGCONFIG, normalize_text(query))


def count_indexed_matches(session: Session, query: str) -> int | None:
    if session.get_bind().dialect.name != "postgresql":
        return None
    document = _postgres_search_document()
    tsquery = _postgres_tsquery(query)
    statement = select(func.count()).select_from(ContentItem).where(
        ContentItem.status == "published",
        ContentItem.is_indexed.is_(True),
        document.op("@@")(tsquery),
    )
    return int(session.scalar(statement) or 0)


def list_indexed_content(session: Session, query: str | None = None, *, candidate_limit: int = 300) -> list[ContentItem]:
    statement = select(ContentItem).where(ContentItem.status == "published", ContentItem.is_indexed.is_(True))

    # Production is PostgreSQL-only. Use a GIN-backed, Arabic-normalized full-text
    # index to bound the more expensive transparent application ranking stage.
    # SQLite remains a deterministic dev/test fallback.
    bind = session.get_bind()
    if query and bind.dialect.name == "postgresql":
        document = _postgres_search_document()
        tsquery = _postgres_tsquery(query)
        statement = (
            statement.where(document.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(document, tsquery).desc(), ContentItem.published_at.desc().nullslast(), ContentItem.slug.asc())
            .limit(candidate_limit)
        )
    else:
        statement = statement.order_by(ContentItem.published_at.desc().nullslast(), ContentItem.slug.asc())

    return list(session.scalars(statement).all())


def get_published_content(session: Session, slug: str) -> ContentItem | None:
    statement = (
        select(ContentItem)
        .where(ContentItem.slug == slug, ContentItem.status == "published")
        .options(selectinload(ContentItem.sources), selectinload(ContentItem.claims))
    )
    return session.scalar(statement)
