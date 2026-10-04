import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'الأبحاث' };

export default function ResearchPage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Research</p>
        <h1>الأبحاث والتحقيق</h1>
        <p>مساحة مهيأة لفصل السؤال البحثي عن الأدلة والنتائج والمراجعة.</p>
      </header>
      <div className="workflow-list" role="list">
        {['سؤال أو فرضية', 'أدلة ومصادر', 'تحليل ومراجعة', 'مخرج قابل للاستشهاد'].map((step, index) => (
          <div className="workflow-item" role="listitem" key={step}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
