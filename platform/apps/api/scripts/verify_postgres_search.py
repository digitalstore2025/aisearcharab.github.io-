from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session

from aisearcharab_api.models import ContentItem
from aisearcharab_api.repository import (
    _postgres_search_document,
    _postgres_tsquery,
    count_indexed_matches,
    list_indexed_content,
)

SLUG = "ci-arabic-fts-normalization"
INDEX_NAME = "ix_content_items_search_fts"


def main() -> int:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine) as session:
        session.execute(delete(ContentItem).where(ContentItem.slug == SLUG))
        session.add(
            ContentItem(
                slug=SLUG,
                url_path=f"/ci/{SLUG}/",
                title="إدارة اَلذَّكَاءِ الإصطناعي عربياً",
                summary="اختبار تكامل لفهرسة الألف والهمزات والحركات العربية.",
                body="هذا سجل مؤقت لاختبار التطبيع في PostgreSQL ثم يتم حذفه.",
                section="reports",
                language="ar",
                status="published",
                is_indexed=True,
                source_authority=5.0,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        query = "ادارة الذكاء الاصطناعي"
        matches = list_indexed_content(session, query, candidate_limit=20)
        total = count_indexed_matches(session, query)
        assert any(item.slug == SLUG for item in matches), "Arabic-normalized GIN FTS failed to retrieve the seeded document"
        assert total is not None and total >= 1, "PostgreSQL FTS total-count query failed"

        document = _postgres_search_document()
        tsquery = _postgres_tsquery(query)
        probe = (
            select(ContentItem.id)
            .where(
                ContentItem.status == "published",
                ContentItem.is_indexed.is_(True),
                document.op("@@")(tsquery),
            )
            .limit(20)
        )
        compiled = probe.compile(engine, compile_kwargs={"literal_binds": True})
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan_rows = session.execute(text("EXPLAIN " + str(compiled))).scalars().all()
        plan = "\n".join(str(row) for row in plan_rows)
        assert INDEX_NAME in plan, f"expected PostgreSQL to use {INDEX_NAME}; plan was: {plan}"

        session.execute(delete(ContentItem).where(ContentItem.slug == SLUG))
        session.commit()

    print("PostgreSQL Arabic-normalized FTS integration and index-usage probes passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
