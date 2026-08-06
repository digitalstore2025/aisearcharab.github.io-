- [ ] نجاح CI (build + tests)
- [ ] مراجعة تقرير gitleaks (artifact) — لا نتائج حساسة أو تم تدويرها
- [ ] تشغيل محلي: `python -m unittest discover -s tests -v`
- [ ] تشغيل local scan: `python3 scripts/scan_data.py`
- [ ] تشغيل pre-commit محلياً: `pre-commit run --all-files`
- [ ] تحقق من أن القوالب تعالج المحتوى بشكل آمن (no unescaped HTML)
- [ ] تفعيل حماية الفرع الرئيسي (Require PR reviews, Require status checks)

## ملاحظات للمراجع
- إذا ظهر أي نتيجة حقيقية في تقرير gitleaks: قم بتدوير/إبطال المفاتيح المتأثرة فوراً ولا تدمج التغييرات حتى يتم تنفيذ ذلك.
- أي تغييرات على التاريخ (git history) يجب تنسيقها مع كل المساهمين.
