import Link from 'next/link';

export default function NotFound() {
  return (
    <main id="main-content" className="shell-width section-block">
      <section className="empty-state">
        <span className="empty-kicker">404</span>
        <h1>الصفحة غير موجودة</h1>
        <p>المسار المطلوب غير متاح ضمن واجهة AISearch الحالية.</p>
        <div className="hero-actions">
          <Link className="button button-primary" href="/">الصفحة الرئيسية</Link>
          <Link className="button button-secondary" href="/search">البحث</Link>
        </div>
      </section>
    </main>
  );
}
