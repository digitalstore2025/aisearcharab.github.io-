import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'البحث' };

export default function SearchPage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Search</p>
        <h1>البحث العربي</h1>
        <p>واجهة البحث جاهزة، لكن الاتصال ببيانات الإنتاج سيأتي في مرحلة Data Architecture.</p>
      </header>
      <form className="search-shell" action="/search" method="get">
        <label htmlFor="q">الاستعلام</label>
        <div className="search-row">
          <input id="q" name="q" type="search" placeholder="ابحث في المصادر الموثقة…" autoComplete="off" />
          <button type="submit">بحث</button>
        </div>
        <p className="field-note">هذه الواجهة لا ترسل البيانات إلى نموذج لغوي ولا إلى خدمة خارجية.</p>
      </form>
    </section>
  );
}
