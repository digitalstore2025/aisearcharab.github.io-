# AISearcharab Platform

هذا المسار يطوّر المنصة الديناميكية دون استبدال واجهة Hugo العامة أو إعلان الجاهزية الإنتاجية قبل اكتمال Staging والمراجعات المستقلة وخطة الرجوع.

## المرحلة الحالية: Phase 3.1+ — Hardening + GEO measurement

القدرات التالية **منفذة في الكود ومغطاة بدرجات مختلفة من CI**، لكنها لا تعني أن بيئة Production الخارجية موجودة أو verified:

- FastAPI modular monolith مع PostgreSQL وAlembic.
- بحث عربي معجمي شفاف مع PostgreSQL GIN FTS مطبّع للعربية وbounded candidate retrieval.
- fallback محلي في واجهة Hugo عند غياب API.
- جلسات Opaque داخل HttpOnly cookies، CSRF وSameSite=Strict.
- Scrypt versioned password hashes مع transparent rehash وserver-side idle timeout.
- TOTP MFA مستقلة للحسابات `owner` و`admin` و`publisher` عند تفعيل سياسة privileged MFA، وهي إلزامية في Staging/Production configuration.
- أسرار TOTP مشفرة at rest بمفتاح بيئي خارجي `MFA_ENCRYPTION_KEY`، ولا يجوز تخزين المفتاح الحقيقي في Git.
- منع إعادة استخدام TOTP المقبول عبر counter محفوظ، وأكواد استرداد عالية العشوائية أحادية الاستخدام تُخزن كـSHA-256 digests وتُعرض plaintext مرة واحدة عند الإنشاء/التجديد.
- Password Step-up re-authentication قصيرة العمر للعمليات الحساسة؛ تبقى defense-in-depth ولا تُعامل كعامل MFA ثانٍ.
- RBAC للأدوار: owner, admin, editor, reviewer, publisher, analyst.
- Separation of Duties اختياري في التطوير وإجباري في Production configuration.
- optimistic locking + row locks + actor provenance لدورة التحرير.
- دورة draft → reviewed → published → archived، مع إبطال المراجعة عند التعديل.
- Trusted Host validation، request-size ceiling، security headers وprivacy-minimized JSON request telemetry.
- migration-aware readiness في Staging/Production.
- Login throttling قبل المصادقة، persistent في قاعدة البيانات، مع Trusted Proxy CIDRs صريحة ومعالجة محافظة لسلاسل `X-Forwarded-For`.
- Tenant-scoped GEO organizations/projects/query sets/evidence infrastructure.
- Ollama وGPT-OSS provider adapters للاختبار/القياس الداخلي ضمن حدود واضحة؛ هذه ليست دليلاً على وجود public generated-answer/RAG product.
- Docker multi-stage runtime يعتمد dependency graph مولداً ومثبت digest ومراجعاً بالـhashes.
- CI: tests، PostgreSQL integration، Arabic FTS probe، OpenAPI pin، secret scanning، dependency drift، `pip-audit --require-hashes --strict`، CycloneDX SBOM، Compose/container smoke وfail-closed release evidence.

## Staging ليس Development آخر

Staging وProduction يُعاملان كبيئات secure runtime في الإعدادات:

- CORS origins يجب أن تستخدم HTTPS.
- SQLite مرفوض؛ PostgreSQL مطلوب لبيئة release-equivalent.
- wildcard hosts مرفوضة.
- placeholder database credentials مثل `change-me` مرفوضة.
- Secure cookies مفعلة.
- privileged MFA ومفتاح MFA وlogin-throttle key مطلوبة.

هذه القيود لا تثبت أن Staging الخارجي موجود؛ هي تمنع تشغيل نسخة “Staging” مخففة ثم تقديمها كدليل إنتاجي.

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

هذا المسار Development فقط. لا تستخدم إعدادات localhost/HTTP/SQLite كدليل Staging أو Production.

### MFA للحسابات المميزة

في Staging/Production يجب ضبط:

```text
REQUIRE_MFA_FOR_PRIVILEGED=true
MFA_ENCRYPTION_KEY=<secret-manager value with at least 32 random bytes>
MFA_ENROLLMENT_TTL_MINUTES=10
MFA_ISSUER=AISearcharab.com
LOGIN_THROTTLE_KEY=<secret-manager value with at least 32 random bytes>
```

بعد password login، الحساب المميز الذي لم يسجل MFA لا يحصل على وصول فعلي إلى `/auth/me` أو مسارات الإدارة حتى يتم تسجيل TOTP وتأكيد الرمز. لوحة الإدارة same-origin تقود عملية التسجيل، وتعرض مفتاح `otpauth` وأكواد الاسترداد فقط أثناء التدفق التفاعلي؛ لا تستخدم LocalStorage/SessionStorage لهذه المواد.

المسارات الأساسية:

- `GET /v1/auth/mfa/status`
- `POST /v1/auth/mfa/enroll/start`
- `POST /v1/auth/mfa/enroll/confirm`
- `POST /v1/auth/mfa/verify`
- `POST /v1/auth/mfa/recovery-codes/regenerate`
- `POST /v1/auth/mfa/disable`

تجديد أكواد الاسترداد وتعطيل MFA يتطلبان جلسة MFA مكتملة وPassword Step-up. تعطيل MFA مرفوض للحسابات المميزة عندما تكون السياسة الإلزامية مفعلة.

### Step-up للعمليات الحساسة

حتى بعد MFA، تسجيل الدخول لا يمنح تلقائياً صلاحية تنفيذ العمليات privileged. عند محاولة إنشاء/تعديل مستخدم، نشر/أرشفة مادة، أو تحويل ادعاء إلى `published`، يطلب الخادم إعادة التحقق بكلمة مرور الحساب عبر `POST /v1/auth/step-up` مع CSRF صحيح. بعد النجاح تصبح الجلسة elevated لمدة `STEP_UP_TTL_MINUTES` فقط، وبحد أقصى حتى انتهاء الجلسة الأصلية.

### Reverse proxies وLogin throttling

`TRUSTED_PROXY_CIDRS` يبقى فارغاً ما لم توجد شبكة Proxy معروفة ومحددة. عند تركه فارغاً تُهمل forwarding headers كمصدر هوية. لا تستخدم `0.0.0.0/0` أو `::/0` أو مجموعة شبكات تغطي عائلة IP كاملة.

Application throttling لا يغني عن distributed edge rate limiting/WAF في Production.

## ربط البحث العام بالـAPI في Preview

اترك `params.apiBaseURL` فارغاً عندما لا توجد بيئة API معتمدة. في معاينة Hugo شغّل البناء مع:

```bash
HUGO_PARAMS_APIBASEURL=https://preview-api.example.com hugo --minify --gc
```

إذا تعذر الـAPI، يعود البحث تلقائياً إلى `/index.json` المحلي.

## موفرو النماذج الداخليون

المستودع يحتوي adapters محكومة مثل Ollama/GPT-OSS لأغراض القياس والاختبار داخل مسار GEO/benchmarking. السياسة الحالية:

- لا تعتبر `answer_text` دليلاً تحريرياً.
- لا توجد مطالبة بأن هذه adapters تشكل public RAG أو public answer engine.
- Ollama endpoint configuration-controlled ومقيد بمضيف/منفذ مسموح، بلا redirects وبحدود timeout/response size.
- أي توسيع نحو arbitrary external fetching أو public generated answers يحتاج threat model/evals/provenance/rollback منفصلة.

## اختبار Load/Latency في Staging

بعد تجهيز مجموعة استعلامات عربية مراجعة بشرياً وبيئة Staging حقيقية:

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

الأداة تطبع مقاييس مجمعة فقط ولا تطبع نصوص الاستعلامات أو أجسام الاستجابات. نتيجة محلية أو synthetic fixture لا تكفي لإغلاق بوابة Production search quality.

## وثائق الإطلاق

- `../docs/PERFECT-MASTER-2026.md` — النموذج الهندسي، الحوكمة وبوابات الجاهزية.
- `../docs/PRODUCTION-ARCHITECTURE-2026.md` — عقد البنية الخارجية وStaging parity.
- `../docs/STAGING-RELEASE-RUNBOOK-2026.md` — تشغيل Staging وفحوص الأمن/MFA/البحث/الحمولة وخطة rollback.
- `../docs/SECURITY_AUDIT_FULL.md` — التدقيق الحالي والـblockers الموثقة.

## ما يزال غير مثبت كقدرة Production

- لا public RAG/vector/generated-answer product surface مثبت.
- لا crawling عام أو arbitrary user-controlled URL fetching.
- لا مدفوعات.
- لا نشر Production تلقائي أو GO تلقائي من CI.
- TOTP MFA منفذة في الكود، لكن يلزم إثباتها فعلياً في Staging ومراجعتها أمنياً بصورة مستقلة.
- distributed rate limiting/WAF، managed PostgreSQL مع PITR/restore drill، benchmark عربي حقيقي، external observability، مراجعة إتاحة مستقلة وStaging/rollback موثق ما زالت بوابات خارجية.
- GitHub `main` ما زال `protected=false` وفق آخر فحص live موثق؛ Issue #65/PR #66 يتابعان حوكمة الفرع.

الحالة لا تُرفع إلى `PRODUCTION_READY` بسبب اسم مرحلة أو وثيقة أو CI أخضر؛ تحتاج جميع أدلة الإصدار المطلوبة.
