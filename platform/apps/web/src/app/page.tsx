import Image from 'next/image';
import Link from 'next/link';
import { APP_META } from '@/lib/app-meta';

const capabilities = [
  ['البحث', 'واجهة بحث عربية مبنية لتكون قابلة للقياس والتتبع قبل إدخال RAG.'],
  ['المصادر', 'مساحة واضحة لفصل المصدر، الدليل، والادعاء بدلاً من خلطها مع المخرجات.'],
  ['الأبحاث', 'بنية عمل قابلة للتوسع للتحقيقات، المراجعة، والتوثيق.'],
] as const;

export default function HomePage() {
  return (
    <main id="main-content">
      <section className="home-hero">
        <div className="shell-width hero-grid">
          <div>
            <p className="eyebrow">{APP_META.phase}</p>
            <h1>{APP_META.name}</h1>
            <p className="hero-intro">{APP_META.description}</p>
            <div className="hero-actions">
              <Link className="button button-primary" href="/dashboard">فتح مساحة العمل</Link>
              <Link className="button button-secondary" href="/search">استكشاف البحث</Link>
            </div>
            <ul className="trust-list" aria-label="مبادئ المرحلة الحالية">
              <li>Server-first</li>
              <li>Evidence before generation</li>
              <li>Security gates by default</li>
            </ul>
          </div>
          <aside className="hero-panel" aria-label="حالة المنصة">
            <div className="hero-brand-mark">
              <Image src="/brand-mark.svg" width={64} height={64} alt="" aria-hidden="true" />
            </div>
            <p className="panel-label">Foundation status</p>
            <h2>واجهة تشغيلية، لا ادعاءات AI وهمية</h2>
            <p>المسارات الأساسية جاهزة بصرياً ومعمارياً. البيانات، المصادقة، وطبقة الذكاء الاصطناعي تبقى خلف بواباتها اللاحقة.</p>
          </aside>
        </div>
      </section>
      <section className="section-block shell-width" aria-labelledby="capabilities-title">
        <div className="section-heading">
          <p className="eyebrow">Chapters 2–5</p>
          <h2 id="capabilities-title">أساس واجهة يمكن البناء فوقه</h2>
        </div>
        <div className="card-grid">
          {capabilities.map(([title, description]) => (
            <article className="info-card" key={title}>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
