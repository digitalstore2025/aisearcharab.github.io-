export type Lang = "en" | "ar" | "tr";

type Copy = {
  nav: readonly [string, string, string, string];
  heroKicker: string;
  heroTitle: string;
  heroBody: string;
  cta: string;
  secondary: string;
  trust: string;
  section: string;
  cards: readonly (readonly [string, string])[];
  programs: string;
  programCards: readonly (readonly [string, string, string])[];
  pricing: string;
  priceCards: readonly (readonly [string, string, string])[];
  footer: string;
  startAssessment: string;
  contactPlan: string;
  curriculum: string;
  plans: string;
  aiTeacher: string;
  dashboardLabel: string;
  studyPath: string;
  lessons: string;
  accuracy: string;
  streak: string;
  coach: string;
  coachBody: string;
  diagnostic: string;
  assessmentTitle: string;
  assessmentBody: string;
  assessmentQuestion: string;
  assessmentSubmit: string;
  assessmentRetry: string;
  assessmentResult: string;
  assessmentLevels: readonly [string, string, string];
  languageLabel: string;
  primaryNavLabel: string;
};

export const languageNames: Record<Lang, string> = {
  en: "English",
  ar: "العربية",
  tr: "Türkçe",
};

export const copy: Record<Lang, Copy> = {
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
    startAssessment: "Start with assessment →",
    contactPlan: "Contact us about this plan",
    curriculum: "Curriculum",
    plans: "Plans",
    aiTeacher: "AI + teacher",
    dashboardLabel: "Learning dashboard preview",
    studyPath: "Study Path",
    lessons: "Lessons",
    accuracy: "Accuracy",
    streak: "Day streak",
    coach: "AI Study Coach",
    coachBody: "Practice with feedback. Escalate nuance to your teacher.",
    diagnostic: "Free diagnostic",
    assessmentTitle: "Find your starting point in 10 minutes.",
    assessmentBody: "Answer five short questions. Your score provides a lightweight starting estimate, not a certified CEFR result.",
    assessmentQuestion: "Question",
    assessmentSubmit: "See my result",
    assessmentRetry: "Try again",
    assessmentResult: "Estimated starting band",
    assessmentLevels: ["Foundation (A1–A2)", "Developing (B1)", "Independent (B2+)"],
    languageLabel: "Language",
    primaryNavLabel: "Primary navigation",
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
    startAssessment: "ابدأ باختبار المستوى ←",
    contactPlan: "تواصل معنا حول هذه الخطة",
    curriculum: "المنهج",
    plans: "الخطط",
    aiTeacher: "الذكاء الاصطناعي + المدرس",
    dashboardLabel: "معاينة لوحة التعلم",
    studyPath: "مسار الدراسة",
    lessons: "دروس",
    accuracy: "الدقة",
    streak: "أيام متتالية",
    coach: "مدرب الدراسة بالذكاء الاصطناعي",
    coachBody: "تدرّب بتغذية راجعة، وارجع للمدرس عند الحاجة إلى حكم لغوي أو سياقي.",
    diagnostic: "اختبار تشخيصي مجاني",
    assessmentTitle: "اعرف نقطة البداية خلال دقائق.",
    assessmentBody: "أجب عن خمسة أسئلة قصيرة. النتيجة تقدير أولي لبداية المسار وليست شهادة CEFR معتمدة.",
    assessmentQuestion: "السؤال",
    assessmentSubmit: "اعرض نتيجتي",
    assessmentRetry: "أعد الاختبار",
    assessmentResult: "النطاق المبدئي المقدر",
    assessmentLevels: ["تأسيسي (A1–A2)", "متوسط نامٍ (B1)", "مستقل (B2+)"],
    languageLabel: "اللغة",
    primaryNavLabel: "التنقل الرئيسي",
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
    startAssessment: "Seviye testiyle başla →",
    contactPlan: "Bu plan için bizimle iletişime geçin",
    curriculum: "Müfredat",
    plans: "Planlar",
    aiTeacher: "AI + öğretmen",
    dashboardLabel: "Öğrenme paneli önizlemesi",
    studyPath: "Çalışma Yolu",
    lessons: "Ders",
    accuracy: "Doğruluk",
    streak: "Günlük seri",
    coach: "AI Çalışma Koçu",
    coachBody: "Geri bildirimle pratik yapın; nüans ve değerlendirme için öğretmene başvurun.",
    diagnostic: "Ücretsiz tanılama",
    assessmentTitle: "Başlangıç noktanızı birkaç dakikada bulun.",
    assessmentBody: "Beş kısa soruyu yanıtlayın. Sonuç başlangıç için hafif bir tahmindir; onaylı bir CEFR sonucu değildir.",
    assessmentQuestion: "Soru",
    assessmentSubmit: "Sonucumu göster",
    assessmentRetry: "Tekrar dene",
    assessmentResult: "Tahmini başlangıç bandı",
    assessmentLevels: ["Temel (A1–A2)", "Gelişen (B1)", "Bağımsız (B2+)"],
    languageLabel: "Dil",
    primaryNavLabel: "Ana gezinme",
  },
};