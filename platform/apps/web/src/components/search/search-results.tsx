import Link from 'next/link';
import type { SearchRequest } from '@/lib/search-request';
import { SEARCH_MAX_PAGE } from '@/lib/search-request';
import { publicContentUrl, searchContent, SearchUnavailableError } from '@/server/api/search';

function pageUrl(query: string, page: number): string {
  const params = new URLSearchParams({ q: query, page: String(page) });
  return `/search?${params.toString()}`;
}

export async function SearchResults({ request }: { request: SearchRequest }) {
  if (request.status === 'idle') {
    return <div className="search-message">اكتب استعلاماً لبدء البحث في المحتوى المنشور والمفهرس.</div>;
  }
  if (request.status === 'invalid') {
    return <div className="search-message search-message-warning">{request.message}</div>;
  }

  try {
    const response = await searchContent(request.query, request.offset);
    const totalPages = Math.max(1, Math.min(SEARCH_MAX_PAGE, Math.ceil(response.total / response.limit)));
    return (
      <div className="results-stack">
        <div className="results-meta" aria-live="polite">
          <span>{response.total} نتيجة</span>
          <span>{response.took_ms.toFixed(1)} ms</span>
          <span>{response.algorithm_version}</span>
        </div>
        {response.results.length ? (
          <ol className="results-list">
            {response.results.map((result) => (
              <li key={result.slug}>
                <article className="result-card">
                  <div className="result-meta"><span>{result.section}</span><span>{result.language}</span></div>
                  <h2><a href={publicContentUrl(result.url)}>{result.title}</a></h2>
                  <p>{result.summary}</p>
                  <div className="result-evidence">
                    <span>Score {result.score.toFixed(3)}</span>
                    <span>Source authority {result.source_authority.toFixed(2)}</span>
                    <span>{result.matched_fields.join(' · ')}</span>
                  </div>
                </article>
              </li>
            ))}
          </ol>
        ) : (
          <div className="search-message">لا توجد نتائج مطابقة في المحتوى المنشور حالياً.</div>
        )}
        {totalPages > 1 ? (
          <nav className="pagination" aria-label="صفحات نتائج البحث">
            {request.page > 1 ? <Link href={pageUrl(request.query, request.page - 1)}>السابق</Link> : <span aria-disabled="true">السابق</span>}
            <strong>صفحة {request.page} من {totalPages}</strong>
            {request.page < totalPages ? <Link href={pageUrl(request.query, request.page + 1)}>التالي</Link> : <span aria-disabled="true">التالي</span>}
          </nav>
        ) : null}
      </div>
    );
  } catch (error) {
    if (error instanceof SearchUnavailableError) {
      return <div className="search-message search-message-warning">خدمة البحث غير متاحة في هذه البيئة حالياً. لم يتم إرسال الاستعلام إلى أي مزود بديل.</div>;
    }
    throw error;
  }
}

export function SearchResultsSkeleton() {
  return (
    <div className="results-skeleton" aria-label="جار تحميل نتائج البحث" aria-busy="true">
      <span /><span /><span />
    </div>
  );
}
