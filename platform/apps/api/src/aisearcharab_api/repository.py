from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import ContentItem


def list_indexed_content(session: Session) -> list[ContentItem]:
    statement = (
        select(ContentItem)
        .where(ContentItem.status == "published", ContentItem.is_indexed.is_(True))
        .order_by(ContentItem.published_at.desc().nullslast(), ContentItem.slug.asc())
    )
    return list(session.scalars(statement).all())


def get_published_content(session: Session, slug: str) -> ContentItem | None:
    statement = (
        select(ContentItem)
        .where(ContentItem.slug == slug, ContentItem.status == "published")
        .options(selectinload(ContentItem.sources), selectinload(ContentItem.claims))
    )
    return session.scalar(statement)
