# AISearcharab Platform

هذا المسار يطوّر المنصة ديناميكياً دون استبدال واجهة Hugo العامة أو إعلان الجاهزية الإنتاجية قبل اكتمال Staging والمراجعات المستقلة وخطة الرجوع.

## المرحلة الحالية: Phase 3.2 — Grounded Assistant Beta

- FastAPI modular monolith مع PostgreSQL وAlembic.
- بحث عربي معجمي شفاف مع PostgreSQL GIN FTS مطبّع للعربية وbounded candidate retrieval.
- fallback محلي في واجهة Hugo عند غياب API.
- جلسات Opaque داخل HttpOnly cookies، CSRF double-submit وSameSite=Strict.
- Scrypt versioned password hashes مع transparent rehash وserver-side idle timeout.
- TOTP MFA مستقلة للحسابات `owner` و`admin` و`publisher` عند تفعيل سياسة privileged MFA، وهي إلزامية في Staging/Production configuration.
- أسرار TOTP مشفرة at rest بمفتاح بيئي خارجي `MFA_ENCRYPTION_KEY`، ولا يجوز تخزين المفتاح الحقيقي في Git.
- منع إعادة استخدام TOTP المقبول عبر counter محفوظ، وأكواد استرداد عالية العشوائية أحادية الاستخدام تُخزن كـSHA-256 digests وتُعرض plaintext مرة واحدة عند الإنشاء/التجديد.
- password step-up re-authentication قصيرة العمر للعمليات الحساسة؛ نافذتها الافتراضية 10 دقائق ولا يمكن أن تتجاوز انتهاء الجلسة. الـStep-up يبقى defense-in-depth إضافياً ولا يُعامل كعامل MFA ثانٍ.
- RBAC للأدوار: owner, admin, editor, reviewer, publisher, analyst.
- Separation of Duties اختياري في التطوير وإجباري في production configuration.
- optimistic locking + row locks + actor provenance لدورة التحرير.
- دورة draft → reviewed → published → archived، مع إبطال المراجعة عند التعديل.
- Grounded Generated Answers اختيارية ومعطلة افتراضياً؛ النموذج يختار `claim_key` فقط من claims مراجَعة، والخادم يعيد بناء الإجابة من النص المراجع مع citations وuncertainty وprovider provenance.
- quota دائمة لكل مستخدم، bounds على المدخلات والمصادر، `store=False`، وإعادة تحقق من evidence بعد زمن المزود قبل إرجاع الإجابة.
- واجهة `/assistant/` عربية RTL للمستخدم المصرح له، تعتمد same-origin session + CSRF ولا تخزن session/CSRF/API secrets في Web Storage.
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

ثم افتح `http://localhost:8000/admin/` للإدارة، أو `http://localhost:8000/assistant/` للمساعد البحثي.

### Grounded Assistant Beta

الميزة معطلة افتراضياً. في بيئة تطوير/اختبار أو Staging معتمدة فقط، اضبط القيم عبر البيئة/Secret Manager:

```text
GENERATED_ANSWERS_ENABLED=true
OPENAI_API_KEY=<secret-manager value>
OPENAI_MODEL=<approved model identifier>
GENERATED_ANSWER_MAX_REQUESTS=20
GENERATED_ANSWER_WINDOW_SECONDS=3600
```

المسار المدفوع `POST /v1/answers/grounded` يتطلب جلسة مصادقاً عليها وصلاحية `content:read` وCSRF صحيحاً. لا توجد anonymous generation endpoint. تفعيل Generated Answers في `production` ما يزال مرفوضاً برمجياً إلى أن تكتمل بوابات التشغيل المستقلة.

### MFA للحسابات المميزة

في Staging/Production يجب ضبط:

```text
REQUIRE_MFA_FOR_PRIVILEGED=true
MFA_ENCRYPTION_KEY=<secret-manager value with at least 32 random bytes>
MFA_ENROLLMENT_TTL_MINUTES=10
MFA_ISSUER=AISearcharab.com
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

حتى بعد MFA، تسجيل الدخول لا يمنح تلقائياً صلاحية تنفيذ عمليات privileged. عند محاولة إنشاء/تعديل مستخدم، نشر/أرشفة مادة، أو تحويل ادعاء إلى `published`، يطلب الخادم إعادة التحقق بكلمة مرور الحساب عبر `POST /v1/auth/step-up` مع CSRF صحيح. بعد النجاح تصبح الجلسة elevated لمدة `STEP_UP_TTL_MINUTES` فقط، وبحد أقصى حتى انتهاء الجلسة الأصلية. المحاولات الفاشلة تدخل في عداد القفل نفسه، وقد تؤدي إلى قفل الحساب وإبطال الجلسة عند بلوغ الحد.

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
- `../docs/STAGING-RELEASE-RUNBOOK-2026.md` — تشغيل Staging، فحوص الأمن/MFA/البحث/الحمولة وخطة rollback.

## بوابات غير مفتوحة بعد

- لا تفعيل Production للمساعد المولد حتى إثبات rate limiting/observability/secrets/runtime في Staging وإزالة production gate بتغيير مستقل ومراجع.
- لا anonymous/public paid generation قبل abuse policy وWAF/rate limits مناسبة.
- لا embeddings أو vector search قبل Golden Dataset ومقارنة قابلة للإعادة.
- لا crawling خارجي قبل allowlist وحماية SSRF وحدود الشبكة والحجم والمهلة وإعادة التوجيه.
- لا مدفوعات.
- لا نشر إنتاجي تلقائي.
- TOTP MFA نُفذت على مستوى الكود، لكن Production ما يزال يتطلب إثباتها فعلياً في Staging ومراجعتها أمنياً بصورة مستقلة، إضافة إلى distributed rate limiting/WAF، managed PostgreSQL مع PITR/restore drill، benchmark عربي حقيقي، external observability، مراجعة إتاحة مستقلة وStaging/rollback موثق.
