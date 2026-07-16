# aisearcharab.com — Data Documentation

## مبنى المجلدات

```
data/
├── sources/       # مصادر البيانات الأولية
├── claims/        # الادعاءات والحقائق
└── entities/      # الكيانات (أشخاص، منظمات، إلخ)
```

## المصادر (sources/)

تحتوي على تعريفات شاملة لكل مصدر معلومات مستخدم في التحقيقات.

### الحقول المطلوبة:

| الحقل | النوع | الوصف |
|--------|--------|-------|
| `id` | string | معرف مستقر (kebab-case) |
| `title` | string | عنوان المصدر |
| `publisher` | string | جهة النشر |
| `url` | string | الرابط الأصلي (HTTP/HTTPS) |
| `accessed_at` | datetime | تاريخ الوصول (ISO 8601) |
| `source_type` | enum | نوع المصدر |
| `language` | string | اللغة (ISO 639-1) |
| `reliability` | enum | درجة الموثوقية |

### حقول اختيارية:

| الحق�� | النوع | الوصف |
|--------|--------|-------|
| `archive_url` | string/null | رابط النسخة المؤرشفة |
| `published_at` | datetime/null | تاريخ النشر الأصلي |
| `integrity` | object/null | بيانات السلامة (SHA-256) |
| `notes` | string/null | ملاحظات إضافية |

### أنواع المصادر:

- `official-document` — وثائق رسمية
- `dataset` — مجموعات بيانات
- `webpage` — صفحات ويب عامة
- `social-post` — منشورات وسائل التواصل
- `interview` — مقابلات
- `media-report` — تقارير إعلامية
- `academic-paper` — أوراق أكاديمية
- `legal-record` — وثائق قانونية
- `other` — أخرى

### درجات الموثوقية:

- `primary` — مصدر أصلي مباشر
- `secondary` — نقل أو تلخيص من مصدر أولي
- `tertiary` — جمع من مصادر ثانوية
- `unverified` — مصدر غير موثوق

### مثال:

```json
{
  "id": "bbc-article-2026-01",
  "title": "Breaking News Article",
  "publisher": "BBC",
  "url": "https://www.bbc.com/news/article",
  "archive_url": "https://web.archive.org/web/*/https://www.bbc.com/news/article",
  "published_at": "2026-01-15T09:00:00Z",
  "accessed_at": "2026-01-15T14:30:00+03:00",
  "source_type": "media-report",
  "language": "en",
  "reliability": "primary",
  "integrity": {
    "sha256": null,
    "local_copy": false
  },
  "notes": "Verified news outlet with editorial standards"
}
```

## الادعاءات (claims/)

تمثل الحقائق والتقديرات والاستنتاجات المستخدمة في التحقيقات.

### الحقول المطلوبة:

| الحقل | النوع | الوصف |
|--------|--------|-------|
| `id` | string | معرف مستقر (kebab-case) |
| `text` | string | نص الادعاء |
| `claim_type` | enum | نوع الادعاء |
| `confidence` | enum | مستوى الثقة |
| `sources` | array | معرفات المصادر الداعمة |
| `review_status` | enum | حالة المراجعة |
| `verified_at` | datetime | تاريخ التحقق (ISO 8601) |

### حقول اختيارية:

| الحقل | النوع | الوصف |
|--------|--------|-------|
| `reviewer` | string/null | معرف المراجع |
| `notes` | string/null | ملاحظات إضافية |

### أنواع الادعاءات:

- `verified-fact` — حقيقة موثقة
- `estimate` — تقدير أو توقع
- `inference` — استنتاج من أدلة
- `third-party-claim` — ادعاء منسوب لطرف آخر

### مستويات الثقة:

- `high` — ثقة عالية (أدلة قوية)
- `medium` — ثقة متوسطة (أدلة معقولة)
- `low` — ثقة منخفضة (أدلة محدودة)
- `unverified` — غير موثوق

### حالات المراجعة:

- `draft` — مسودة أولية
- `reviewed` — تمت المراجعة
- `published` — منشورة
- `rejected` — مرفوضة

### مثال:

```json
{
  "id": "gdp-growth-2025",
  "text": "GDP grew by 3.5% in 2025 according to official reports.",
  "claim_type": "verified-fact",
  "confidence": "high",
  "sources": ["gov-report-2026-01", "imf-database"],
  "review_status": "published",
  "verified_at": "2026-01-10T10:00:00Z",
  "reviewer": "economist-001",
  "notes": "Official government statistics verified against IMF data"
}
```

## الكيانات (entities/)

تمثل الأشخاص والمنظمات والأماكن والمشاريع المهمة.

### الحقول المطلوبة:

| الحقل | النوع | الوصف |
|--------|--------|-------|
| `id` | string | معرف مستقر (kebab-case) |
| `name` | string | الاسم الرسمي |
| `entity_type` | enum | نوع الكيان |
| `status` | enum | حالة الكيان |
| `aliases` | array | الأسماء البديلة |

### حقول اختيارية:

| الحقل | النوع | الوصف |
|--------|--------|-------|
| `description` | string/null | وصف الكيان |
| `source_ids` | array/null | معرفات المصادر الموثقة |

### أنواع الكيانات:

- `person` — شخص
- `organization` — منظمة
- `company` — شركة
- `government` — جهة حكومية
- `location` — مكان جغرافي
- `project` — مشروع
- `other` — أخرى

### حالات الكيانات:

- `active` — نشط
- `inactive` — غير نشط
- `unknown` — غير معروف

### مثال:

```json
{
  "id": "tech-corp-inc",
  "name": "TechCorp International Inc.",
  "entity_type": "company",
  "status": "active",
  "aliases": ["TechCorp", "TECI", "Tech Corporation"],
  "description": "Global technology company founded in 1995, specializing in AI and cloud services",
  "source_ids": ["company-registry-2026", "tech-news-001"]
}
```

## التحقق والصيانة

### التحقق المحلي

```bash
python scripts/validate_data.py
```

### التحقق عبر CI/CD

يتم تشغيل التحقق تلقائياً على كل push و pull request.

### الأخطاء الشائعة

| الخطأ | السبب | الحل |
|--------|--------|-------|
| `id must match filename` | المعرف لا يطابق اسم الملف | تأكد من تطابق المعرف مع اسم الملف |
| `unknown source ids` | مصدر غير موجود | أضف المصدر أولاً إلى `sources/` |
| `invalid ISO 8601 datetime` | تاريخ بصيغة خاطئة | استخدم `2026-01-15T09:00:00Z` |
| `invalid language code` | كود اللغة خاطئ | استخدم ISO 639-1: `ar`, `en`, `fr` |

---

للمزيد من المعلومات، راجع `AGENTS.md` و `EXECUTIVE_BLUEPRINT.md`.
