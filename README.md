# AISearcharab.com — مرصد الذكاء الاصطناعي العربي

منصة عربية **Static-First** للبحث والرصد والتحليل في الذكاء الاصطناعي، مع محتوى تحريري قابل للتدقيق، وسجل واضح للمصادر والادعاءات والقيود والتصحيحات، ومسار ديناميكي منفصل للمزايا التي تحتاج API ومصادقة وقاعدة بيانات.

## الحالة الحالية

### الواجهة العامة الثابتة

المستودع ينفذ واجهة Hugo عامة منخفضة السطح الهجومي تشمل:

- موقعاً عربياً وRTL افتراضياً.
- تحقيقات وأدلة أدوات ومنهجية وتصحيحات.
- سجلات منظمة للمصادر والادعاءات والكيانات.
- بحثاً محلياً ثابتاً مع تطبيع عربي وترتيب قابل للاختبار.
- بيانات Schema.org بحسب نوع الصفحة.
- canonical وsitemap وrobots وRSS وبيانات المشاركة.
- PWA وأصولاً عامة يتم التحقق منها في CI.
- اختبارات Python، تحققاً من البيانات والمخرجات، وميزانيات أداء ثابتة.

### المنصة الديناميكية داخل `platform/`

يوجد أيضاً تنفيذ برمجي منفصل لا يستبدل الواجهة العامة الثابتة ولا يثبت بذاته الجاهزية الإنتاجية:

- FastAPI modular monolith.
- PostgreSQL وAlembic migrations وبحث PostgreSQL FTS عربي.
- جلسات Opaque داخل HttpOnly cookies، CSRF، RBAC وSeparation of Duties.
- TOTP MFA للحسابات المميزة وسياسات password step-up للعمليات الحساسة.
- دورة تحرير ومراجعة ونشر مع provenance وoptimistic locking/row locking.
- Grounded Generated Answers اختيارية ومعطلة افتراضياً، مع claims مراجعة وcitations وprovider provenance وإعادة تحقق من evidence.
- واجهتا `/admin/` و`/assistant/` same-origin.
- request-size limits وTrusted Host validation وsecurity headers وtelemetry مقيدة الخصوصية.
- CI خاص بالـAPI يشمل tests وPostgreSQL integration وdependency audit وSBOM وcontainer smoke وrelease-evidence gates.

راجع `platform/README.md` للتفاصيل والقيود التشغيلية.

## ما لم يُثبت إنتاجياً بعد

وجود الكود والاختبارات لا يعني أن Production أصبح جاهزاً. تظل بوابات خارجية وتشغيلية منفصلة، منها على الأقل:

- حماية `main` فعلياً عبر Branch Protection أو Ruleset؛ الحالة الحية في 2026-09-05 ما تزال `protected=false`.
- HTTPS Staging حقيقي مع إعدادات وأسرار خارج المستودع.
- distributed rate limiting/WAF مناسب للمسارات الديناميكية والمدفوعة.
- managed PostgreSQL مع backup/PITR وrestore drill موثق.
- observability خارجية واختبارات load/latency على Staging.
- benchmark عربي حقيقي ومراجعة جودة بشرية مستقلة.
- مراجعة أمنية وإتاحة مستقلة وخطة rollback مثبتة.
- موافقة بشرية صريحة قبل أي تفعيل Production للمساعد المولد.

لا تُحوّل هذه البنود إلى PASS اعتماداً على وجود ملف أو نجاح اختبار محلي فقط.

## التحقق المحلي

يتطلب Hugo بالإصدار المعتمد في CI وPython 3.12:

```bash
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/validate_data.py
python scripts/validate_production_integrity.py
hugo --minify --gc
python scripts/validate_build.py
python scripts/validate_pwa.py
```

اختبارات المنصة الديناميكية وبواباتها موثقة داخل `platform/README.md` و`.github/workflows/platform-api.yml`.

## بنية أساسية

```text
content/          المحتوى التحريري
data/             المصادر والادعاءات والكيانات العامة
layouts/          قوالب Hugo وSchema.org
static/           CSS وJavaScript والأصول العامة
scripts/          أدوات التحقق
schemas/          JSON Schema
tests/            اختبارات الموقع والبيانات
platform/         API والمصادقة وقاعدة البيانات والمساعد المقيّد
engineering/      أدوات الجاهزية والتقييم الهندسي
docs/             المعمارية والحوكمة والتدقيق
.github/workflows CI والنشر والبوابات الأمنية
```

## سلامة البيانات والادعاءات

- لا تُنشر قيمة اختبار أو ادعاء مختلق في `data/`.
- لا تُحفظ بيانات حساسة أو هويات مصادر بشرية في المستودع العام.
- لا تُعامل مخرجات الذكاء الاصطناعي كدليل.
- كل ادعاء منشور يحتاج إلى مصدر قابل للفحص وحالة مراجعة واضحة.
- حالة Production وRelease Evidence يجب أن تبقى fail-closed ما لم تكن الأدلة الخارجية الحالية متاحة وقابلة للتحقق.

راجع:

- `docs/EXECUTIVE_BLUEPRINT.md`
- `docs/ADR-001-PRODUCT-AND-ARCHITECTURE.md`
- `docs/BRANCH_GOVERNANCE.md`
- `IMPLEMENTATION_STATUS.md`
- `AGENTS.md`
- `SECURITY.md`
