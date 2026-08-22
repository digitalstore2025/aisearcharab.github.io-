# AISearcharab.com — مرصد الذكاء الاصطناعي العربي

منصة عربية **Static-First** للبحث والرصد والتحليل في الذكاء الاصطناعي، مع محتوى تحريري قابل للتدقيق، وسجل واضح للمصادر والادعاءات والقيود والتصحيحات.

## الحالة الحالية — Evidence First

هذا المستودع يحتوي مسارين مختلفين يجب عدم الخلط بينهما:

### 1) الواجهة العامة الثابتة

منفذة ومختبرة داخل المستودع:

- موقع Hugo ثابت، عربي وRTL افتراضياً.
- تحقيقات وأدلة أدوات ومنهجية وتصحيحات.
- سجلات منظمة للمصادر والادعاءات والكيانات.
- بحث محلي ثابت مع تطبيع عربي وترتيب حتمي.
- Schema.org وcanonical وsitemap وrobots وRSS وبيانات مشاركة.
- هوية مؤسسية responsive مع اختبارات تحقق وميزانيات أداء.
- GitHub Actions وGitHub Pages ونطاق مخصص.

### 2) المنصة الديناميكية داخل `platform/`

منفذة على مستوى الكود وCI، لكنها **ليست مثبتة كبيئة Production خارجية**:

- FastAPI + PostgreSQL + Alembic.
- بحث عربي معجمي وPostgreSQL FTS.
- لوحة إدارة ومسارات تحرير محكومة.
- جلسات opaque، CSRF، RBAC، Password Step-up وTOTP MFA للحسابات المميزة وفق إعدادات البيئة.
- Login throttling مستمر في قاعدة البيانات مع دعم reverse proxies الموثوقة فقط.
- Tenant-scoped GEO workspaces وطبقة أدلة/قياس.
- موفرا Ollama/GPT-OSS مضبوطَان للاختبار والقياس الداخلي؛ وجودهما لا يعني وجود منتج عام للإجابات المولدة أو RAG.
- اختبارات API/PostgreSQL/migrations/container، dependency audit، SBOM وrelease evidence fail-closed.

الحالة الخارجية تبقى أقل من `PRODUCTION_READY` حتى توجد أدلة Staging/Production حقيقية. نجاح CI يثبت تكامل المستودع فقط، وليس تشغيل البنية الخارجية.

## ما لا يجوز الادعاء بأنه جاهز حالياً

لا توجد أدلة كافية في المستودع وحده لإعلان ما يلي كقدرات Production مكتملة:

- **Public RAG / vector search / generated-answer product surface**.
- زاحف ويب عام أو fetch تعسفي لعناوين يحددها المستخدم.
- مدفوعات أو اشتراكات.
- Managed PostgreSQL مع PITR وrestore drill مثبتين خارجياً.
- WAF وdistributed rate limiting مثبتان في Staging/Production.
- external observability/alerting مثبتة.
- benchmark عربي حقيقي بالحجم المطلوب للإطلاق.
- مراجعة مستقلة كاملة للأمن والإتاحة.
- `PRODUCTION_READY` أو أي تسمية مكافئة.

## Blockers موثقة

- GitHub ما زال يبلغ أن فرع `main` غير محمي (`protected=false`). هذا **blocker لحوكمة الإصدار** حتى يتم تفعيل Branch Protection أو Ruleset فعلي والتحقق منه. راجع Issue #65 وPR #66.
- توجد مراجعات خارجية وتجارب Staging/rollback/restore/observability ما زالت مطلوبة وفق `docs/PRODUCTION-ARCHITECTURE-2026.md`.
- أي مشكلة UX مفتوحة تبقى منفصلة عن ادعاءات الأمن أو Production readiness؛ لا تُخفى لإنتاج صورة زائفة عن الاكتمال.

## التحقق المحلي — الواجهة الثابتة

يتطلب Hugo بالإصدار المعتمد في CI وPython 3.12:

```bash
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/validate_data.py
hugo --minify --gc
python scripts/validate_build.py
```

## التحقق المحلي — المنصة الديناميكية

```bash
cd platform/apps/api
python -m pip install -e '.[dev]'
python -m compileall -q src tests scripts alembic
python -m pytest
```

تكامل PostgreSQL والمهاجرات والحاوية وسلسلة التوريد يُتحقق منه في GitHub Actions؛ لا تعتبر اختبار SQLite محلياً بديلاً عن PostgreSQL أو Staging.

## بنية أساسية

```text
content/              المحتوى التحريري
data/                 المصادر والادعاءات والكيانات العامة
layouts/              قوالب Hugo وSchema.org
static/               CSS وJavaScript والأصول العامة
scripts/              أدوات التحقق الثابتة
tests/                اختبارات الواجهة/البيانات
platform/             FastAPI/PostgreSQL/Admin/GEO والاختبارات الديناميكية
docs/                 المعمارية والحوكمة والتدقيق
.github/workflows/     CI والنشر وبوابات الأدلة
```

## سلامة البيانات والادعاءات

- لا تُنشر قيمة اختبار أو ادعاء مختلق في `data/`.
- لا تُحفظ بيانات حساسة أو هويات مصادر بشرية في المستودع العام.
- لا تُعامل مخرجات الذكاء الاصطناعي كدليل.
- كل ادعاء منشور يحتاج إلى مصدر قابل للفحص وحالة مراجعة واضحة.
- لا تُحوّل حالة `IMPLEMENTED` أو CI أخضر إلى ادعاء `PRODUCTION_READY` دون أدلة خارجية مستقلة.

راجع:

- `docs/EXECUTIVE_BLUEPRINT.md`
- `docs/PRODUCTION-ARCHITECTURE-2026.md`
- `docs/PERFECT-MASTER-2026.md`
- `docs/SECURITY_AUDIT_FULL.md`
- `AGENTS.md`
- `SECURITY.md`
