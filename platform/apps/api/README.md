# AISearcharab API — Phase 2

واجهة API فعلية لمرحلة الاسترجاع والبحث المعجمي القابل للقياس. هذه المرحلة لا تولّد إجابات، ولا تنفّذ RAG، ولا مدفوعات، ولا حسابات مستخدمين.

## التشغيل المحلي

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp ../../.env.example .env
alembic upgrade head
uvicorn aisearcharab_api.main:app --reload
```

## الفحوص

```bash
pytest
python scripts/evaluate_search.py
```

## حدود المرحلة

- البحث: lexical retrieval فقط، مع تطبيع عربي ودرجات شفافة.
- البيانات: PostgreSQL إنتاجياً وSQLite للاختبارات المحلية.
- لا تُستخدم بيانات الاختبار خارج `tests/fixtures/`.
- لا يوجد توليد نصوص أو استدعاء نموذج لغوي في هذا الإصدار.

## خصوصية تحليلات البحث

تسجيل الاستعلامات معطل افتراضياً. عند تفعيله يجب ضبط `QUERY_HASH_KEY` بقيمة عشوائية لا تقل عن 32 بايت؛ لا يُخزّن نص الاستعلام، بل HMAC-SHA-256 فقط مع عدد النتائج والزمن.
