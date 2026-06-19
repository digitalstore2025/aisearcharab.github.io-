# aisearcharab.com — The 2026 Investigative Hub

منصة عربية متخصصة في الصحافة الاستقصائية الرقمية، التحقق، OSINT، تحليل البيانات، وهندسة أدوات البحث المدعومة بالذكاء الاصطناعي.

## الحالة التنفيذية

تم بناء MVP كامل يعتمد Hugo وGitHub Pages ويشمل:

- واجهة عربية RTL متجاوبة.
- أقسام التحقيقات والأدوات والمنهجية والتصحيحات.
- نماذج بيانات للمصادر والادعاءات والكيانات.
- JSON Schemas مرجعية.
- Validator بلغة Python واختبارات تلقائية.
- JSON Search Index ثابت.
- Schema.org أساسي.
- سياسات الخصوصية والأمان وشروط الاستخدام.
- GitHub Actions للبناء والتحقق والنشر.

## التشغيل المحلي

```bash
python -m unittest discover -s tests -v
python scripts/validate_data.py
hugo server -D
```

## البناء الإنتاجي

```bash
hugo --minify --gc
```

## المراجع

- [`docs/EXECUTIVE_BLUEPRINT.md`](docs/EXECUTIVE_BLUEPRINT.md)
- [`AGENTS.md`](AGENTS.md)
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md)

## المعمارية

```text
content/          # التحقيقات والأدلة والسياسات
 data/             # المصادر والادعاءات والكيانات
 schemas/          # عقود JSON المرجعية
 layouts/          # قوالب Hugo وSchema.org وSearch JSON
 static/           # CSS وCNAME
 scripts/          # التحقق من البيانات
 tests/            # اختبارات المستودع
 .github/workflows # CI/CD
```

## قواعد النشر

1. لا معلومة بلا مصدر قابل للفحص.
2. لا استنتاج يُقدَّم كحقيقة.
3. لا بيانات حساسة داخل المستودع العام.
4. لا مخرجات AI تحريرية دون مراجعة بشرية.
5. لا دمج قبل نجاح البناء والاختبارات.

## ملاحظة

السجلات التي تحمل أسماء `example-*` أو `sample-*` تعليمية فقط ويجب استبدالها قبل استخدامها في مادة صحفية حقيقية.
