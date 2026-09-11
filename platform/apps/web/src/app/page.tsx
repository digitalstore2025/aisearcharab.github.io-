import { APP_META } from '@/lib/app-meta';

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">{APP_META.phase}</p>
        <h1 id="page-title">{APP_META.name}</h1>
        <p>{APP_META.description}</p>
        <p className="status">Web foundation is active. AI, RAG, and authentication are intentionally disabled in this phase.</p>
      </section>
    </main>
  );
}
