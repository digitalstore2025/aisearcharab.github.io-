# AISearcharab API

واجهة API للاسترجاع التحريري المحكوم والبحث المعجمي، مع **Grounded Generated Answers** كقدرة Beta اختيارية ومعطلة افتراضياً. المدفوعات والزحف الخارجي غير مفعّلين.

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

## البحث والاسترجاع

- البحث العام: lexical retrieval مع تطبيع عربي ودرجات شفافة.
- البيانات: PostgreSQL إنتاجياً وSQLite للاختبارات المحلية.
- لا تُستخدم بيانات الاختبار خارج `tests/fixtures/`.
- واجهة Hugo تبقى قادرة على الرجوع إلى الفهرس المحلي إذا تعطل الـAPI.

## Grounded Generated Answers — Beta

المسار:

```text
POST /v1/answers/grounded
```

هذه القدرة:

- **معطلة افتراضياً** عبر `GENERATED_ANSWERS_ENABLED=false`.
- تتطلب جلسة مصادقاً عليها تحمل `content:read`، إضافة إلى CSRF token صالح لأن الاستدعاء يستهلك مورداً مدفوعاً؛ ليست endpoint عامة مجهولة حالياً.
- تسترجع فقط محتوى AISearcharab المنشور والمفهرس، ولا تقوم بجلب URLs خارجية.
- تعامل محتوى الأدلة كبيانات غير موثوقة، لا كتعليمات للنموذج.
- تستخدم OpenAI Responses API مع Structured Outputs و`store=False`.
- لا تقبل إلا Response مكتملة (`status=completed`).
- تتحقق محلياً من JSON ومن أن كل `evidence_id` أعاده النموذج موجود فعلاً في مجموعة الأدلة المسترجعة.
- تضيف `model`, `request_id`, `usage` وبيانات الروابط على الخادم بدلاً من الوثوق بأن النموذج سيولدها بصورة صحيحة.
- تفشل مغلقةً إذا كانت الأدلة غير كافية أو إذا أعاد النموذج citation غير معروف أو output لا يطابق العقد.
- تطبق quota دائمة لكل مستخدم عبر `audit_events`. في PostgreSQL تُسلسل الحجوزات لنفس المستخدم بقفل row-level قبل تسجيل الحجز، ثم يتم `commit` قبل أي اتصال بالشبكة.
- تسجل نتائج generation كـaudit events مع `model`, latency, uncertainty وعدادات الاستخدام العددية (`input_units`, `output_units`, `total_units`) من دون تسجيل نص السؤال أو الأسرار.
- تُحوّل حالات provider غير المتوقعة إلى أخطاء API محكومة بدلاً من تسريبها كـ500 غير مصنف.

### تفعيلها

ضع القيم عبر بيئة التشغيل/Secret Manager، لا داخل Git:

```bash
GENERATED_ANSWERS_ENABLED=true
OPENAI_API_KEY=<secret-manager-value>
OPENAI_MODEL=gpt-5.6-terra
GENERATED_ANSWER_MAX_REQUESTS=20
GENERATED_ANSWER_WINDOW_SECONDS=3600
```

الحدود التشغيلية الافتراضية موثقة في `platform/.env.example`: مهلة، retries، أقصى output tokens، عدد مصادر، حجم evidence لكل مصدر، وعدد requests لكل نافذة زمنية.

> **Production activation محظور برمجياً في هذه النسخة.** تم تنفيذ distributed per-user request limiting وaudit-based cost/error observability، لكن `Settings.validate()` يظل fail-closed في production إلى أن تمر هذه الضوابط عبر CI/security/runtime verification ويتم حقن السر من Secret Manager. فتح endpoint للعامة يحتاج طبقة abuse policy مستقلة قبل إزالة المصادقة/CSRF.

## خصوصية تحليلات البحث

تسجيل الاستعلامات معطل افتراضياً. عند تفعيله يجب ضبط `QUERY_HASH_KEY` بقيمة عشوائية لا تقل عن 32 بايت؛ لا يُخزّن نص الاستعلام، بل HMAC-SHA-256 فقط مع عدد النتائج والزمن.
