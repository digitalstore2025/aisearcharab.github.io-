from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from aisearcharab_api.models import ContentItem
from aisearcharab_api.repository import count_indexed_matches, list_indexed_content

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
        assert any(item.slug == SLUG for item in matches), (
            "Arabic-normalized PostgreSQL FTS failed to retrieve the seeded document"
        )
        assert total is not None and total >= 1, "PostgreSQL FTS total-count query failed"

        index_state = session.execute(
            text(
                """
                SELECT
                    i.indisvalid,
                    i.indisready,
                    am.amname AS access_method,
                    pg_get_indexdef(i.indexrelid) AS index_definition,
                    pg_get_expr(i.indpred, i.indrelid) AS index_predicate
                FROM pg_index AS i
                JOIN pg_class AS c ON c.oid = i.indexrelid
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                JOIN pg_am AS am ON am.oid = c.relam
                WHERE n.nspname = 'public' AND c.relname = :index_name
                """
            ),
            {"index_name": INDEX_NAME},
        ).one_or_none()
        assert index_state is not None, f"missing PostgreSQL index {INDEX_NAME}"
        assert bool(index_state.indisvalid), f"PostgreSQL index {INDEX_NAME} is not valid"
        assert bool(index_state.indisready), f"PostgreSQL index {INDEX_NAME} is not ready"
        assert index_state.access_method == "gin", f"PostgreSQL index {INDEX_NAME} must use GIN"

        indexdef = " ".join(str(index_state.index_definition or "").lower().split())
        predicate = " ".join(str(index_state.index_predicate or "").lower().split())
        assert "to_tsvector" in indexdef, f"PostgreSQL index {INDEX_NAME} must index a tsvector"
        assert "translate" in indexdef, f"PostgreSQL index {INDEX_NAME} must normalize Arabic text"
        assert "status" in predicate and "published" in predicate, (
            f"PostgreSQL index {INDEX_NAME} must be restricted to published content; predicate={predicate}"
        )
        assert "is_indexed" in predicate and "true" in predicate, (
            f"PostgreSQL index {INDEX_NAME} must be restricted to indexable content; predicate={predicate}"
        )

        session.execute(delete(ContentItem).where(ContentItem.slug == SLUG))
        session.commit()

    print("PostgreSQL Arabic-normalized FTS retrieval and index-integrity probes passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
