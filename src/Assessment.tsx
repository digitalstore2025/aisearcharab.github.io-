import { FormEvent, useMemo, useState } from "react";
import type { Lang } from "./copy";
import { copy } from "./copy";

type Question = {
  prompt: string;
  options: readonly string[];
  answer: number;
};

const questions: Record<Lang, readonly Question[]> = {
  en: [
    { prompt: "Choose the correct sentence.", options: ["She go to work every day.", "She goes to work every day.", "She going to work every day."], answer: 1 },
    { prompt: "Complete: I have lived here ___ 2022.", options: ["for", "since", "during"], answer: 1 },
    { prompt: "Which word is closest to ‘reliable’ ?", options: ["dependable", "temporary", "unclear"], answer: 0 },
    { prompt: "Choose the best response: ‘Would you mind sending the file again?’", options: ["Not at all. I’ll resend it now.", "Yes, I mind the file.", "I am send yesterday."], answer: 0 },
    { prompt: "Choose the most natural sentence.", options: ["If I had known, I would have called you.", "If I knew, I would called you.", "If I had know, I will call you."], answer: 0 },
  ],
  ar: [
    { prompt: "اختر الجملة الإنجليزية الصحيحة.", options: ["She go to work every day.", "She goes to work every day.", "She going to work every day."], answer: 1 },
    { prompt: "أكمل: I have lived here ___ 2022.", options: ["for", "since", "during"], answer: 1 },
    { prompt: "ما الكلمة الأقرب إلى reliable؟", options: ["dependable", "temporary", "unclear"], answer: 0 },
    { prompt: "اختر أفضل رد على: Would you mind sending the file again?", options: ["Not at all. I’ll resend it now.", "Yes, I mind the file.", "I am send yesterday."], answer: 0 },
    { prompt: "اختر الجملة الأكثر طبيعية.", options: ["If I had known, I would have called you.", "If I knew, I would called you.", "If I had know, I will call you."], answer: 0 },
  ],
  tr: [
    { prompt: "Doğru İngilizce cümleyi seçin.", options: ["She go to work every day.", "She goes to work every day.", "She going to work every day."], answer: 1 },
    { prompt: "Tamamlayın: I have lived here ___ 2022.", options: ["for", "since", "during"], answer: 1 },
    { prompt: "‘Reliable’ kelimesine en yakın seçenek hangisi?", options: ["dependable", "temporary", "unclear"], answer: 0 },
    { prompt: "En iyi yanıtı seçin: ‘Would you mind sending the file again?’", options: ["Not at all. I’ll resend it now.", "Yes, I mind the file.", "I am send yesterday."], answer: 0 },
    { prompt: "En doğal cümleyi seçin.", options: ["If I had known, I would have called you.", "If I knew, I would called you.", "If I had know, I will call you."], answer: 0 },
  ],
};

export function Assessment({ lang }: { lang: Lang }) {
  const t = copy[lang];
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [score, setScore] = useState<number | null>(null);
  const currentQuestions = questions[lang];
  const complete = currentQuestions.every((_, index) => answers[index] !== undefined);

  const result = useMemo(() => {
    if (score === null) return null;
    if (score <= 2) return t.assessmentLevels[0];
    if (score <= 4) return t.assessmentLevels[1];
    return t.assessmentLevels[2];
  }, [score, t.assessmentLevels]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!complete) return;
    const nextScore = currentQuestions.reduce(
      (total, question, index) => total + (answers[index] === question.answer ? 1 : 0),
      0,
    );
    setScore(nextScore);
  };

  const reset = () => {
    setAnswers({});
    setScore(null);
  };

  return (
    <section className="assessment shell" id="assessment" aria-labelledby="assessment-title">
      <div>
        <span className="eyebrow">{t.diagnostic}</span>
        <h2 id="assessment-title">{t.assessmentTitle}</h2>
        <p>{t.assessmentBody}</p>
      </div>
      <div className="assessment-panel">
        {score === null ? (
          <form onSubmit={submit}>
            {currentQuestions.map((question, index) => (
              <fieldset key={question.prompt}>
                <legend>{t.assessmentQuestion} {index + 1}: {question.prompt}</legend>
                {question.options.map((option, optionIndex) => {
                  const id = `q-${index}-${optionIndex}`;
                  return (
                    <label className="answer" htmlFor={id} key={option}>
                      <input
                        id={id}
                        name={`question-${index}`}
                        type="radio"
                        checked={answers[index] === optionIndex}
                        onChange={() => setAnswers((current) => ({ ...current, [index]: optionIndex }))}
                      />
                      <span dir="ltr">{option}</span>
                    </label>
                  );
                })}
              </fieldset>
            ))}
            <button className="button light" type="submit" disabled={!complete}>{t.assessmentSubmit}</button>
          </form>
        ) : (
          <div className="assessment-result" role="status" aria-live="polite">
            <span>{t.assessmentResult}</span>
            <strong>{result}</strong>
            <small>{score}/5</small>
            <button className="button light" type="button" onClick={reset}>{t.assessmentRetry}</button>
          </div>
        )}
      </div>
    </section>
  );
}