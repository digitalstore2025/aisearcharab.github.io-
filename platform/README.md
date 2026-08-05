# AISearcharab Platform

هذا المسار يطوّر المنصة ديناميكياً دون استبدال واجهة Hugo العامة قبل اكتمال الاختبارات وخطة الرجوع.

## المرحلة المنفذة: Phase 3 — Governed Editorial Preview

- FastAPI modular monolith.
- PostgreSQL وAlembic migrations.
- بحث عربي معجمي قابل للقياس مع fallback محلي في واجهة Hugo.
- تسجيل دخول بجلسات Opaque داخل HttpOnly cookies.
- CSRF double-submit token وSameSite=Strict.
- كلمات مرور Scrypt وسياسة قفل بعد المحاولات الفاشلة.
- RBAC للأدوار: owner, admin, editor, reviewer, publisher, analyst.
- دورة تحرير draft → reviewed → published → archived.
- مصادر وادعاءات منظمة وسجل تدقيق لا يخزن أسراراً.
- لوحة إدارة عربية بلا مكتبات طرف ثالث أو سكربتات خارجية.

## التشغيل المحلي

```bash
cp .env.example .env
# غيّر POSTGRES_PASSWORD قبل التشغيل
docker compose up --build
```

بعد تطبيق migrations، أنشئ المالك الأول من داخل حاوية API أو بيئة Python الموثوقة:

```bash
python apps/api/scripts/bootstrap_admin.py --email owner@example.com --name "اسم المالك"
```

ثم افتح `http://localhost:8000/admin/`.

## ربط البحث العام بالـAPI في Preview

اترك `params.apiBaseURL` فارغاً في الإنتاج الحالي. في معاينة Hugo شغّل البناء مع:

```bash
HUGO_PARAMS_APIBASEURL=https://preview-api.example.com hugo --minify --gc
```

إذا تعذر الـAPI، يعود البحث تلقائياً إلى `/index.json` المحلي.

## بوابات غير مفتوحة

- لا RAG أو إجابات مولدة.
- لا embeddings أو vector search.
- لا crawling خارجي.
- لا مدفوعات.
- لا نشر إنتاجي تلقائي.
