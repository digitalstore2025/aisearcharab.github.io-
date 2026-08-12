import { useMemo, useState } from "react";
import { Assessment } from "./Assessment";
import { copy, languageNames, type Lang } from "./copy";

function App() {
  const [lang, setLang] = useState<Lang>("en");
  const t = copy[lang];
  const dir = lang === "ar" ? "rtl" : "ltr";
  const languageName = useMemo(() => languageNames[lang], [lang]);

  return (
    <div className="page" dir={dir} lang={lang}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="header shell">
        <a className="brand" href="#top" aria-label="AIsearch.study home">
          <span className="mark">AI</span><span>search.study</span>
        </a>
        <nav className="nav" aria-label={t.primaryNavLabel}>
          <a href="#programs">{t.nav[0]}</a>
          <a href="#lab">{t.nav[1]}</a>
          <a href="#assessment">{t.nav[2]}</a>
          <a href="#pricing">{t.nav[3]}</a>
        </nav>
        <label className="language">
          <span className="sr-only">{t.languageLabel}</span>
          <select value={lang} onChange={(event) => setLang(event.target.value as Lang)} aria-label={t.languageLabel}>
            <option value="en">English</option>
            <option value="ar">العربية</option>
            <option value="tr">Türkçe</option>
          </select>
        </label>
      </header>

      <main id="main-content">
        <section className="hero shell" id="top">
          <div className="hero-copy">
            <div className="eyebrow">{t.heroKicker}</div>
            <h1>{t.heroTitle}</h1>
            <p className="lead">{t.heroBody}</p>
            <div className="actions">
              <a className="button primary" href="#assessment">{t.cta}</a>
              <a className="button ghost" href="#programs">{t.secondary}</a>
            </div>
            <div className="trust">{t.trust} · {languageName}</div>
          </div>
          <div className="hero-card" aria-label={t.dashboardLabel}>
            <div className="card-top"><span>{t.studyPath}</span><span className="status">B1</span></div>
            <div className="progress" aria-label="68%"><span style={{ width: "68%" }} /></div>
            <div className="metric-grid">
              <div><strong>24</strong><small>{t.lessons}</small></div>
              <div><strong>82%</strong><small>{t.accuracy}</small></div>
              <div><strong>7</strong><small>{t.streak}</small></div>
            </div>
            <div className="coach"><span className="dot" /><div><strong>{t.coach}</strong><p>{t.coachBody}</p></div></div>
          </div>
        </section>

        <section className="section shell" id="lab">
          <div className="section-heading"><span className="eyebrow">{t.aiTeacher}</span><h2>{t.section}</h2></div>
          <div className="grid three">{t.cards.map(([title, body]) => <article className="feature" key={title}><div className="icon" aria-hidden="true">✦</div><h3>{title}</h3><p>{body}</p></article>)}</div>
        </section>

        <section className="section shell" id="programs">
          <div className="section-heading"><span className="eyebrow">{t.curriculum}</span><h2>{t.programs}</h2></div>
          <div className="grid three">{t.programCards.map(([title, level, body]) => <article className="program" key={title}><span className="pill">{level}</span><h3>{title}</h3><p>{body}</p><a href="#assessment">{t.startAssessment}</a></article>)}</div>
        </section>

        <Assessment lang={lang} />

        <section className="section shell" id="pricing">
          <div className="section-heading"><span className="eyebrow">{t.plans}</span><h2>{t.pricing}</h2></div>
          <div className="grid three">{t.priceCards.map(([title, price, body], index) => <article className={`price ${index === 1 ? "featured" : ""}`} key={title}><h3>{title}</h3><div className="amount">{price}</div><p>{body}</p><a className="button block" href={`mailto:hello@aisearch.study?subject=${encodeURIComponent(`AIsearch.study ${title}`)}`}>{t.contactPlan}</a></article>)}</div>
        </section>
      </main>

      <footer className="footer shell"><div className="brand"><span className="mark">AI</span><span>search.study</span></div><p>{t.footer}</p><small>© 2026 AIsearch.study</small></footer>
    </div>
  );
}

export default App;