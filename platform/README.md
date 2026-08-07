# AISearcharab Platform

هذا المسار يطوّر المنصة ديناميكياً دون استبدال واجهة Hugo العامة أو إعلان الجاهزية الإنتاجية قبل اكتمال Staging والمراجعات المستقلة وخطة الرجوع.

## المرحلة الحالية: Phase 3.1 — Perfect Master 2026 Hardening

- FastAPI modular monolith مع PostgreSQL وAlembic.
- بحث عربي معجمي شفاف مع PostgreSQL GIN FTS مطبّع للعربية وbounded candidate retrieval.
- fallback محلي في واجهة Hugo عند غياب API.
- جلسات Opaque داخل HttpOnly cookies، CSRF double-submit وSameSite=Strict.
- Scrypt versioned password hashes مع transparent rehash وserver-side idle timeout.
- RBAC للأدوار: owner, admin, editor, reviewer, publisher, analyst.
- Separation of Duties اختياري في التطوير وإجباري في production configuration.
- optimistic locking + row locks + actor provenance لدورة التحرير.
- دورة draft → reviewed → published → archived، مع إبطال المراجعة عند التعديل.
- Trusted Host validation، request-size ceiling، security headers وprivacy-minimized JSON request telemetry.
- migration-aware readiness في Staging/Production.
- Docker multi-stage runtime يعتمد dependency graph مولداً ومثبت digest ومراجعاً بالـhashes.
- CI: tests، PostgreSQL integration، Arabic FTS probe، OpenAPI pin، secret scanning، dependency drift، `pip-audit --require-hashes --strict`، CycloneDX SBOM، Compose/container smoke.

## التشغيل المحلي

```bash
cp .env.example .env
# غيّر POSTGRES_PASSWORD قبل التشغيل
docker compose up --build
```

بعد تطبيق migrations، أنشئ المالك الأول من داخل حاوية API أو بيئة Python موثوقة:

```bash
python apps/api/scripts/bootstrap_admin.py --email owner@example.com --name "اسم المالك"
```

ثم افتح `http://localhost:8000/admin/`.

## ربط البحث العام بالـAPI في Preview

اترك `params.apiBaseURL` فارغاً عندما لا توجد بيئة API معتمدة. في معاينة Hugo شغّل البناء مع:

```bash
HUGO_PARAMS_APIBASEURL=https://preview-api.example.com hugo --minify --gc
```

إذا تعذر الـAPI، يعود البحث تلقائياً إلى `/index.json` المحلي.

## اختبار Load/Latency في Staging

بعد تجهيز مجموعة استعلامات عربية مراجعة بشرياً:

```bash
cd apps/api
python scripts/load_probe.py \
  --base-url https://preview-api.example.com \
  --queries /secure/path/arabic-benchmark.json \
  --requests 1000 \
  --concurrency 25 \
  --max-p95-ms 750 \
  --max-error-rate 0.01
```

الأداة تطبع مقاييس مجمعة فقط ولا تطبع نصوص الاستعلامات أو أجسام الاستجابات.

## وثائق الإطلاق

- `../docs/PERFECT-MASTER-2026.md` — النموذج الهندسي، الحوكمة وبوابات الجاهزية.
- `../docs/STAGING-RELEASE-RUNBOOK-2026.md` — تشغيل Staging، فحوص الأمن/البحث/الحمولة وخطة rollback.

## بوابات غير مفتوحة بعد

- لا RAG أو إجابات مولدة.
- لا embeddings أو vector search.
- لا crawling خارجي.
- لا مدفوعات.
- لا نشر إنتاجي تلقائي.
- Production ما يزال يتطلب distributed rate limiting/WAF، MFA/step-up للحسابات الحساسة، managed PostgreSQL مع PITR/restore drill، benchmark عربي حقيقي، external observability، مراجعة أمن/إتاحة مستقلة وStaging/rollback موثق.
