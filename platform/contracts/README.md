# Platform API Contract

لا يُحفظ عقد OpenAPI الكامل داخل Git لتجنب بقاء نسخة ضخمة أو قديمة توحي بأنها العقد الحالي. بدلاً من ذلك:

- `openapi.sha256` يثبت بصمة العقد المولد من التطبيق.
- CI يولد `openapi.generated.json` من `create_app()` في كل تشغيل.
- CI يتحقق من صحة JSON ثم يقارن SHA-256 بالبصمة المثبتة.
- النسخة الكاملة تُرفع Artifact لمدة محدودة للمراجعة والتنزيل.

بعد تعديل endpoints أو schemas:

```bash
cd platform/apps/api
python scripts/export_openapi.py --output ../../contracts/openapi.generated.json
sha256sum ../../contracts/openapi.generated.json
```

راجع العقد بصرياً، ثم حدّث `platform/contracts/openapi.sha256` بالبصمة الجديدة واحذف الملف المولد محلياً. لا تعدّل العقد يدوياً.
