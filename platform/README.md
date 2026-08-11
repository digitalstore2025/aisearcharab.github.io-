# AISearcharab Platform

هذا المجلد هو مسار الانتقال المنضبط من الواجهة العامة الثابتة إلى منصة كاملة. لا يحل محل موقع Hugo الحالي في هذه المرحلة.

## المرحلة المنفذة: Phase 2 — Retrieval Foundation

- FastAPI modular monolith.
- PostgreSQL schema وAlembic migration.
- بحث عربي معجمي شفاف وقابل للقياس.
- Content/Source/Claim provenance model.
- Health checks وRequest IDs ورؤوس أمان للـAPI.
- Golden Dataset واختبارات MRR وRecall@5.
- Docker Compose للتطوير المحلي.

## بوابات غير مفتوحة بعد

- **RAG/Generated Answers:** محظور حتى اعتماد Golden Dataset حقيقي، وقياس جودة الاستشهادات، واختبارات Prompt Injection.
- **Payments:** محظور حتى تحديد الكيان القانوني، دولة التحصيل، المنتج، الضرائب، سياسة الاسترداد، المزود، وبيانات Sandbox.
- **Authentication/Admin:** المرحلة التالية بعد مراجعة نموذج الصلاحيات وسياسة البيانات.
- **Crawling:** لا تشغيل قبل allowlist وسياسة robots/ToS وحدود SSRF والحجم والمهلة.

## التشغيل

```bash
cp .env.example .env
# غيّر كلمات المرور قبل التشغيل
docker compose up --build
```
