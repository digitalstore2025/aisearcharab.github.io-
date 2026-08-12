import { useMemo, useState } from "react";

type Lang = "en" | "ar" | "tr";

const copy = {
  en: {
    nav: ["Programs", "AI Study Lab", "Assessment", "Pricing"],
    heroKicker: "English learning built for the AI era",
    heroTitle: "Learn English with a clear path, real practice, and intelligent feedback.",
    heroBody: "AIsearch.study combines teacher-led learning, practical English programs, and AI-assisted study tools for Arabic and Turkish speakers.",
    cta: "Take the free assessment",
    secondary: "Explore programs",
    trust: "English • العربية • Türkçe",
    section: "A learning system, not another content library",
    cards: [
      ["Structured pathways", "Progress from level checks to practical speaking, writing, listening, and workplace English."],
      ["AI Study Lab", "Practice explanations, vocabulary, rewriting, speaking prompts, and guided self-study with guardrails."],
      ["Teacher-led support", "Use AI for repetition and feedback while keeping human guidance for judgment, nuance, and progress."],
    ],
    programs: "Programs",
    programCards: [
      ["General English", "A1–C1", "Everyday communication, grammar, listening, vocabulary, and confidence."],
      ["Professional English", "B1–C1", "Meetings, email, interviews, presentations, and workplace communication."],
      ["English + AI", "All levels", "Learn how to use AI responsibly to study, research, write, and practice English."],
    ],
    pricing: "Start simple",
    priceCards: [
      ["Free", "$0", "Level check, sample lessons, selected AI study tools."],
      ["Learner", "$12/mo", "Full learning tracks, progress history, exercises, and extended AI practice."],
      ["Coached", "$39/mo", "Learner plan plus teacher feedback sessions and personalized study planning."],
    ],
    footer: "AIsearch.study — practical English learning with human guidance and responsible AI.",
  },
  ar: {
    nav: ["البرامج", "مختبر الذكاء الاصطناعي", "اختبار المستوى", "الأسعار"],
    heroKicker: "تعلم الإنجليزية لعصر الذكاء الاصطناعي",
    heroTitle: "تعلم الإنجليزية بمسار واضح، ممارسة حقيقية، وتغذية راجعة ذكية.",
    heroBody: "تجمع AIsearch.study بين الإشراف التعليمي، والبرامج العملية، وأدوات دراسة مدعومة بالذكاء الاصطناعي للناطقين بالعربية والتركية.",
    cta: "ابدأ اختبار المستوى المجاني",
    secondary: "استكشف البرامج",
    trust: "English • العربية • Türkçe",
    section: "نظام تعلم متكامل، وليس مجرد مكتبة محتوى",
    cards: [
      ["مسارات منظمة", "انتقل من تحديد المستوى إلى مهارات التحدث والكتابة والاستماع والإنجليزية المهنية."],
      ["مختبر AI للدراسة", "تدرب على الشرح والمفردات وإعادة الصياغة وأسئلة المحادثة والدراسة الموجهة ضمن ضوابط واضحة."],
      ["إشراف بشري", "استخدم الذكاء الاصطناعي للتكرار والتغذية الراجعة مع إبقاء الحكم اللغوي والتوجيه بيد المدرس."],
    ],
    programs: "البرامج",
    programCards: [
      ["الإنجليزية العامة", "A1–C1", "التواصل اليومي والقواعد والاستماع والمفردات وبناء الثقة."],
      ["الإنجليزية المهنية", "B1–C1", "الاجتماعات والبريد الإلكتروني والمقابلات والعروض والتواصل في بيئة العمل."],
      ["الإنجليزية + الذكاء الاصطناعي", "كل المستويات", "تعلم استخدام AI بصورة مسؤولة للدراسة والبحث والكتابة والممارسة."],
    ],
    pricing: "ابدأ ببساطة",
    priceCards: [
      ["مجاني", "$0", "اختبار مستوى ودروس تجريبية وأدوات AI مختارة."],
      ["متعلم", "$12/شهر", "المسارات الكاملة وسجل التقدم والتمارين وممارسة AI موسعة."],
      ["بإشراف", "$39/شهر", "كل مزايا المتعلم مع جلسات ملاحظات وخطة دراسة شخصية."],
    ],
    footer: "AIsearch.study — تعلم إنجليزية عملي بإشراف بشري وذكاء اصطناعي مسؤول.",
  },
  tr: {
    nav: ["Programlar", "AI Çalışma Laboratuvarı", "Seviye Testi", "Fiyatlar"],
    heroKicker: "Yapay zekâ çağı için İngilizce öğrenimi",
    heroTitle: "Net bir yol, gerçek pratik ve akıllı geri bildirimle İngilizce öğrenin.",
    heroBody: "AIsearch.study; öğretmen rehberliğini, pratik İngilizce programlarını ve yapay zekâ destekli çalışma araçlarını Arapça ve Türkçe konuşan öğrenciler için bir araya getirir.",
    cta: "Ücretsiz seviye testini başlat",
    secondary: "Programları keşfet",
    trust: "English • العربية • Türkçe",
    section: "Sadece içerik değil, bütünlüklü bir öğrenme sistemi",
    cards: [
      ["Yapılandırılmış yollar", "Seviye tespitinden konuşma, yazma, dinleme ve iş İngilizcesine adım adım ilerleyin."],
      ["AI Çalışma Laboratuvarı", "Açıklama, kelime, yeniden yazma, konuşma soruları ve rehberli bireysel çalışma pratiği yapın."],
      ["Öğretmen desteği", "Tekrar ve geri bildirim için yapay zekâyı, karar ve kişisel yönlendirme için insan rehberliğini kullanın."],
    ],
    programs: "Programlar",
    programCards: [
      ["Genel İngilizce", "A1–C1", "Günlük iletişim, dil bilgisi, dinleme, kelime bilgisi ve özgüven."],
      ["Profesyonel İngilizce", "B1–C1", "Toplantılar, e-posta, mülakatlar, sunumlar ve iş iletişimi."],
      ["İngilizce + AI", "Tüm seviyeler", "AI'ı öğrenme, araştırma, yazma ve pratik için sorumlu biçimde kullanın."],
    ],
    pricing: "Basit başlayın",
    priceCards: [
      ["Ücretsiz", "$0", "Seviye kontrolü, örnek dersler ve seçili AI araçları."],
      ["Öğrenci", "$12/ay", "Tam öğrenme yolları, ilerleme geçmişi, alıştırmalar ve geniş AI pratiği."],
      ["Koçluklu", "$39/ay", "Öğrenci planına ek olarak öğretmen geri bildirimi ve kişisel çalışma planı."],
    ],
    footer: "AIsearch.study — insan rehberliği ve sorumlu yapay zekâ ile pratik İngilizce öğrenimi.",
  },
} as const;

function App() {
  const [lang, setLang] = useState<Lang>("en");
  const t = copy[lang];
  const dir = lang === "ar" ? "rtl" : "ltr";
  const languageName = useMemo(() => ({ en: "English", ar: "العربية", tr: "Türkçe" }[lang]), [lang]);

  return (
    <div className="page" dir={dir} lang={lang}>
      <header className="header shell">
        <a className="brand" href="#top" aria-label="AIsearch.study home">
          <span className="mark">AI</span><span>search.study</span>
        </a>
        <nav className="nav" aria-label="Primary">
          <a href="#programs">{t.nav[0]}</a>
          <a href="#lab">{t.nav[1]}</a>
          <a href="#assessment">{t.nav[2]}</a>
          <a href="#pricing">{t.nav[3]}</a>
        </nav>
        <label className="language">
          <span className="sr-only">Language</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label="Language">
            <option value="en">English</option>
            <option value="ar">العربية</option>
            <option value="tr">Türkçe</option>
          </select>
        </label>
      </header>

      <main id="top">
        <section className="hero shell">
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
          <div className="hero-card" aria-label="Learning dashboard preview">
            <div className="card-top"><span>Study Path</span><span className="status">B1</span></div>
            <div className="progress"><span style={{ width: "68%" }} /></div>
            <div className="metric-grid">
              <div><strong>24</strong><small>Lessons</small></div>
              <div><strong>82%</strong><small>Accuracy</small></div>
              <div><strong>7</strong><small>Day streak</small></div>
            </div>
            <div className="coach"><span className="dot" /><div><strong>AI Study Coach</strong><p>Practice with feedback. Escalate nuance to your teacher.</p></div></div>
          </div>
        </section>

        <section className="section shell" id="lab">
          <div className="section-heading"><span className="eyebrow">AI + teacher</span><h2>{t.section}</h2></div>
          <div className="grid three">{t.cards.map(([title, body]) => <article className="feature" key={title}><div className="icon">✦</div><h3>{title}</h3><p>{body}</p></article>)}</div>
        </section>

        <section className="section shell" id="programs">
          <div className="section-heading"><span className="eyebrow">Curriculum</span><h2>{t.programs}</h2></div>
          <div className="grid three">{t.programCards.map(([title, level, body]) => <article className="program" key={title}><span className="pill">{level}</span><h3>{title}</h3><p>{body}</p><a href="#assessment">Start with assessment →</a></article>)}</div>
        </section>

        <section className="assessment shell" id="assessment">
          <div><span className="eyebrow">Free diagnostic</span><h2>Find your starting point in 10 minutes.</h2><p>Vocabulary, grammar, reading, and practical communication. Your result becomes the starting point for your study path.</p></div>
          <a className="button light" href="mailto:hello@aisearch.study?subject=AIsearch.study%20assessment">{t.cta}</a>
        </section>

        <section className="section shell" id="pricing">
          <div className="section-heading"><span className="eyebrow">Plans</span><h2>{t.pricing}</h2></div>
          <div className="grid three">{t.priceCards.map(([title, price, body], index) => <article className={`price ${index === 1 ? "featured" : ""}`} key={title}><h3>{title}</h3><div className="amount">{price}</div><p>{body}</p><a className="button block" href={`mailto:hello@aisearch.study?subject=${encodeURIComponent(`AIsearch.study ${title}`)}`}>Choose plan</a></article>)}</div>
        </section>
      </main>

      <footer className="footer shell"><div className="brand"><span className="mark">AI</span><span>search.study</span></div><p>{t.footer}</p><small>© 2026 AIsearch.study</small></footer>
    </div>
  );
}

export default App;