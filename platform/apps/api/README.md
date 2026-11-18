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
- لا ترسل للنموذج corpus حراً كي يصوغ حقائق؛ ترسل فقط claims مراجَعة (`reviewed`/`published`) ذات confidence معروف من المواد المسترجعة.
- دور النموذج هو **اختيار `claim_key` فقط**. لا يُقبل منه answer factual حر أو paraphrase، وStructured Output يمنع الحقول الإضافية.
- يبني الخادم نص الإجابة من `Claim.text` الأصلي كما هو، مع إظهار `claim_type` و`confidence`، ويشتق citations من المادة التي تملك الـclaim المختار.
- تعامل claims المسترجعة كبيانات غير موثوقة داخل prompt؛ أي تعليمات أو prompt injection داخلها لا تصبح تعليمات تنفيذية.
- تستخدم OpenAI Responses API مع Structured Outputs و`store=False`، ولا تقبل إلا Response مكتملة (`status=completed`).
- تتحقق محلياً من أن كل `claim_key` أعاده النموذج موجود ضمن مجموعة claims المراجَعة المسترجعة، وتفشل مغلقةً عند claim مجهول، أو selection غير متسق مع حالة `insufficient`.
- لا تُرسل `source_urls` إلى النموذج. وتُقيد metadata المعادة للمستخدم بعدد URLs وحجم إجمالي محليين؛ كما يُقيد عدد claims وحجم نص claims المرسل لكل evidence وحجم serialized input الكلي.
- provenance الخاص بالموديل يأتي من `response.model` الذي يعيده المزود، لا من alias المطلوب. غياب/فساد resolved model identifier يؤدي إلى fail-closed بدلاً من ادعاء نسخة غير مثبتة.
- تضيف `request_id`, `usage` وبيانات الروابط على الخادم بدلاً من الوثوق بأن النموذج سيولدها بصورة صحيحة.
- تطبق quota دائمة لكل مستخدم عبر `audit_events`. في PostgreSQL تُسلسل الحجوزات لنفس المستخدم بقفل row-level قبل تسجيل الحجز، ثم يتم `commit` قبل أي اتصال بالشبكة.
- تسجل نتائج generation كـaudit events مع `model`, latency, uncertainty وعدادات الاستخدام العددية (`input_units`, `output_units`, `total_units`) من دون تسجيل نص السؤال أو الأسرار.
- تُحوّل حالات provider غير المتوقعة إلى أخطاء API محكومة بدلاً من تسريبها كـ500 غير مصنف.

### بوابة OpenAI-compatible داخلية (اختيارية)

يمكن توجيه طلبات Responses API إلى بوابة داخلية متوافقة مع OpenAI، مثل FreeLLMAPI، عبر `OPENAI_BASE_URL`. يبقى التكامل معطلاً ما لم تُضبط الإعدادات صراحةً، ولا يغيّر عقد الإجابة المحكومة أو صلاحيات المستخدمين أو حصصهم المحلية.

- اختر `GENERATED_ANSWERS_PROVIDER=openai` لاستخدام `OPENAI_API_KEY` مع نقطة OpenAI الافتراضية، أو `gateway` لاستخدام `OPENAI_BASE_URL` و`OPENAI_GATEWAY_API_KEY` المنفصلين. يفرض عميل HTTP سقفاً افتراضياً قدره 1 MiB (قابل للضبط بين 16 KiB و16 MiB) على جسم الاستجابة أثناء التدفق وقبل تخزينه في الذاكرة؛ يطلب العميل `identity` ويرفض الاستجابات المضغوطة. القيمة الافتراضية `disabled`؛ لا يبدأ التوليد قبل اختيار مزود صريح. يرفض التطبيق خلط مفاتيح المزودين أو تشغيل البوابة دون عنوانها وسرها.
- عند استخدام بوابة غير loopback، اضبط `OPENAI_GATEWAY_ALLOWED_ORIGINS` على الأصل الكامل المسموح به حرفياً بصيغة scheme/host/port؛ يتحقق التطبيق من المنفذ أيضاً ويرفض wildcard أو أي أصل آخر. في Staging/Production يلزم HTTPS وقائمة مطابقة. يجب أيضاً فرض قيود خروج شبكية تمنع الوصول إلى الوجهات العامة؛ قائمة التطبيق ليست بديلاً عن جدار الحماية.
- HTTP مسموح فقط إلى `localhost` أو loopback في التطوير المحلي. لا تضع بيانات اعتماد أو query strings في عنوان URL.
- عند تشغيل API داخل Docker Compose، لا تستخدم `127.0.0.1` للوصول إلى بوابة على المضيف؛ استخدم اسم خدمة البوابة على الشبكة المشتركة مع TLS موثوق وSAN مطابق.
- يجب أن تكون FreeLLMAPI على شبكة خاصة، وألا يتصل بها المتصفح أو العملاء مباشرة. يظل FastAPI هو نقطة الدخول الوحيدة وهو المسؤول عن المصادقة وCSRF والحصص وسجل التدقيق.
- FreeLLMAPI أحادي المستخدم؛ لا تستخدم رمزه الموحد كهوية عميل، ولا تمنح العملاء مفاتيح البوابة. لا تفعّل MCP أو لوحة إدارة FreeLLMAPI على واجهة عامة.
- ثبّت إصداراً محدداً وصورة Docker ببصمة digest، ولا تستخدم `latest` في Staging/Production. لا تمنح الحاوية Docker Socket.
- دعم `/v1/responses` وJSON Schema في البوابة لا يضمن أن كل مزود upstream ينفذ القيود الصارمة بالطريقة نفسها؛ يظل تحقق Pydantic المحلي وفشل الاستجابة غير الصالحة إلزاميين.
- لا يُفترض أن سماح MIT في كود البوابة يمنح حق إعادة بيع خدمات المزودين. افحص شروط كل مزود وسياسة الاحتفاظ بالبيانات قبل أي استخدام تجاري أو إنتاجي.

التفاصيل ومعايير القبول في `docs/FREELLMAPI-INTERNAL-GATEWAY.md`.

### تفعيلها

ضع القيم عبر بيئة التشغيل/Secret Manager، لا داخل Git:

```bash
GENERATED_ANSWERS_ENABLED=true
GENERATED_ANSWERS_PROVIDER=gateway
OPENAI_GATEWAY_API_KEY=<gateway-secret-manager-value>
OPENAI_BASE_URL=https://freellmapi.internal:3443/v1
OPENAI_GATEWAY_ALLOWED_ORIGINS=https://freellmapi.internal:3443
OPENAI_MODEL=<verified-responses-compatible-model>
GENERATED_ANSWER_MAX_REQUESTS=20
GENERATED_ANSWER_WINDOW_SECONDS=3600
```

الحدود التشغيلية الافتراضية موثقة في `platform/.env.example`: مهلة، retries، أقصى output tokens، عدد مصادر، حجم evidence لكل مصدر، وعدد requests لكل نافذة زمنية. توجد أيضاً حدود دفاعية داخلية لعدد claims وروابط المصادر وحجم serialized model input.

> **Production activation محظور برمجياً في هذه النسخة.** تم تنفيذ distributed per-user request limiting وaudit-based cost/error observability، لكن `Settings.validate()` يظل fail-closed في production إلى أن تمر هذه الضوابط عبر CI/security/runtime verification ويتم حقن السر من Secret Manager. فتح endpoint للعامة يحتاج طبقة abuse policy مستقلة قبل إزالة المصادقة/CSRF.

## خصوصية تحليلات البحث

تسجيل الاستعلامات معطل افتراضياً. عند تفعيله يجب ضبط `QUERY_HASH_KEY` بقيمة عشوائية لا تقل عن 32 بايت؛ لا يُخزّن نص الاستعلام، بل HMAC-SHA-256 فقط مع عدد النتائج والزمن.