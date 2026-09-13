import type { Metadata } from 'next';
import { Suspense } from 'react';
import { SearchResults, SearchResultsSkeleton } from '@/components/search/search-results';
import { parseSearchRequest } from '@/lib/search-request';

export const metadata: Metadata = { title: 'البحث' };

type SearchPageProps = Readonly<{
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}>;

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = (await searchParams) ?? {};
  const request = parseSearchRequest(params);

  return (
    <section className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Search</p>
        <h1>البحث العربي</h1>
        <p>استعلامات قابلة للمشاركة عبر URL، وتنفيذ Server-side ضد API المنصة فقط.</p>
      </header>
      <form className="search-shell" action="/search" method="get">
        <label htmlFor="q">الاستعلام</label>
        <div className="search-row">
          <input id="q" name="q" type="search" defaultValue={request.query} minLength={2} maxLength={120} required placeholder="ابحث في المصادر الموثقة…" autoComplete="off" />
          <button type="submit">بحث</button>
        </div>
        <p className="field-note">لا JavaScript مطلوب لإرسال البحث، ولا اتصال مباشر من المتصفح بقاعدة البيانات أو مزود ذكاء اصطناعي.</p>
      </form>
      <Suspense key={`${request.query}:${request.page}`} fallback={<SearchResultsSkeleton />}>
        <SearchResults request={request} />
      </Suspense>
    </section>
  );
}
