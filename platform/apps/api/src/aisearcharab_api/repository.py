from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import ContentItem


def list_indexed_content(session: Session, query: str | None = None, *, candidate_limit: int = 300) -> list[ContentItem]:
    statement = select(ContentItem).where(ContentItem.status == "published", ContentItem.is_indexed.is_(True))

    # Production is PostgreSQL-only. Use its GIN-backed full-text index to bound the
    # expensive application ranking stage. SQLite remains a deterministic dev/test fallback.
    bind = session.get_bind()
    if query and bind.dialect.name == "postgresql":
        document = func.to_tsvector(
            "simple",
            func.coalesce(ContentItem.title, "")
            + " "
            + func.coalesce(ContentItem.summary, "")
            + " "
            + func.coalesce(ContentItem.body, "")
            + " "
            + func.coalesce(ContentItem.section, ""),
        )
        tsquery = func.websearch_to_tsquery("simple", query)
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
