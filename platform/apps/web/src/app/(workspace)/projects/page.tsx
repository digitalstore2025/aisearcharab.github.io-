import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'المشاريع' };

export default function ProjectsPage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Projects</p>
        <h1>المشاريع</h1>
        <p>المسار سيصبح حاوية العمل الأساسية للمصادر والاستعلامات والنتائج بعد إضافة طبقة البيانات.</p>
      </header>
      <div className="empty-state">
        <span className="empty-kicker">Domain model pending</span>
        <h2>الواجهة جاهزة؛ نموذج البيانات لم يُفترض بعد</h2>
        <p>لن ننشئ Projects وهمية قبل تعريف schema وownership وauthorization بصورة قابلة للاختبار.</p>
      </div>
    </section>
  );
}
