export const SEARCH_PAGE_SIZE = 10;
export const SEARCH_MAX_PAGE = 30;

export type SearchRequest = Readonly<{
  query: string;
  page: number;
  offset: number;
  status: 'idle' | 'ready' | 'invalid';
  message?: string;
}>;

type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? '' : value ?? '';
}

export function parseSearchRequest(params: RawSearchParams): SearchRequest {
  const query = first(params.q).trim();
  const rawPage = first(params.page).trim();
  const page = /^\d+$/.test(rawPage) ? Number(rawPage) : 1;

  if (!query) return { query: '', page: 1, offset: 0, status: 'idle' };
  if (query.length < 2) return { query, page: 1, offset: 0, status: 'invalid', message: 'اكتب حرفين على الأقل.' };
  if (query.length > 120) return { query, page: 1, offset: 0, status: 'invalid', message: 'الاستعلام يتجاوز الحد الأقصى المسموح.' };
  if (!Number.isSafeInteger(page) || page < 1 || page > SEARCH_MAX_PAGE) {
    return { query, page: 1, offset: 0, status: 'invalid', message: 'رقم الصفحة غير صالح.' };
  }
  return { query, page, offset: (page - 1) * SEARCH_PAGE_SIZE, status: 'ready' };
}
