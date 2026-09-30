import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'لوحة العمل' };

const metrics = [
  ['5', 'مسارات واجهة أساسية'],
  ['0', 'استدعاءات AI عامة'],
  ['100%', 'Server-first baseline'],
] as const;

export default function DashboardPage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Workspace</p>
        <h1>لوحة العمل</h1>
        <p>ملخص صادق لحالة طبقة الويب قبل توصيل البيانات والمصادقة والذكاء الاصطناعي.</p>
      </header>
      <div className="metric-grid">
        {metrics.map(([value, label]) => (
          <article className="metric-card" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </article>
        ))}
      </div>
      <article className="status-panel">
        <span className="status-dot" aria-hidden="true" />
        <div>
          <h2>Web foundation active</h2>
          <p>Navigation, layout, design tokens, fonts, image handling, and accessibility checks are enabled. Product data remains intentionally disconnected.</p>
        </div>
      </article>
    </section>
  );
}
