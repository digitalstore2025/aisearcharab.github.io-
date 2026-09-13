import { SearchResultsSkeleton } from '@/components/search/search-results';

export default function LoadingSearchPage() {
  return (
    <section className="page-stack" aria-label="جار تجهيز صفحة البحث">
      <div className="page-header"><p className="eyebrow">Search</p><h1>البحث العربي</h1></div>
      <SearchResultsSkeleton />
    </section>
  );
}
