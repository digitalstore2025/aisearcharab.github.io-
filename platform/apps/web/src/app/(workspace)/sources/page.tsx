import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'المصادر' };

export default function SourcesPage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Sources</p>
        <h1>المصادر</h1>
        <p>المسار مخصص لاحقاً لسجل المصادر، حالة التحقق، وسياق الاستشهاد.</p>
      </header>
      <div className="empty-state">
        <span className="empty-kicker">Data gate</span>
        <h2>لا توجد بيانات تجريبية متنكرة كبيانات حقيقية</h2>
        <p>سيتم توصيل هذا المسار إلى Data Access Layer بعد تعريف العقود والصلاحيات والمخططات.</p>
      </div>
    </section>
  );
}
