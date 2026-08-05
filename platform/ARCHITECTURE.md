# Phase 2 Architecture Decision

## القرار

الإبقاء على Hugo كواجهة تحريرية عامة مستقرة، وبناء نواة منصة حقيقية داخل `platform/` كـ modular monolith. يبدأ التنفيذ بخدمة API واسترجاع معجمي مقاس، ولا تُضاف إجابات مولدة أو مدفوعات في هذه المرحلة.

## سبب القرار

1. يمنع كسر الموقع العام أثناء التطوير.
2. يفصل المحتوى المنشور عن الوظائف الديناميكية غير الناضجة.
3. يفرض قياس البحث قبل إدخال embeddings أو reranking أو RAG.
4. يسمح باختبار PostgreSQL والمخططات والصلاحيات تدريجياً.

## تدفق البحث الحالي

```text
HTTP query
→ length validation
→ Arabic/Latin normalization
→ tokenization
→ published/indexed content filter
→ transparent lexical scoring
→ source-authority + bounded freshness bonus
→ paginated ranked documents
```

## القيود الأمنية

- لا fetch خارجي.
- لا تنفيذ أدوات.
- لا نموذج لغوي.
- لا أسرار في المستودع.
- تسجيل الاستعلامات معطل افتراضياً؛ عند تفعيله تُحفظ بصمة HMAC-SHA-256 بمفتاح سري منفصل فقط مع عدد النتائج وزمن الاستجابة، دون نص الاستعلام أو عنوان IP أو حساب مستخدم.
