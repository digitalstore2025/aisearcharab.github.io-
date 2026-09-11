const LOCAL_HTTP_HOSTS = new Set(['localhost', '127.0.0.1', 'api']);

function validateOrigin(raw: string, label: string, allowLocalHttp: boolean): string {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error(`${label} is not a valid URL`);
  }
  if (url.username || url.password || url.search || url.hash) throw new Error(`${label} must be a plain origin without credentials, query, or fragment`);
  if (url.pathname !== '/' && url.pathname !== '') throw new Error(`${label} must not contain a path`);
  const localHttp = allowLocalHttp && url.protocol === 'http:' && LOCAL_HTTP_HOSTS.has(url.hostname);
  if (url.protocol !== 'https:' && !localHttp) throw new Error(`${label} must use HTTPS except for reviewed local/container hosts`);
  return url.origin;
}

export function isSearchEnabled(): boolean {
  return process.env.AISEARCH_SEARCH_ENABLED?.trim().toLowerCase() === 'true';
}

export function getApiBaseUrl(): string | null {
  if (!isSearchEnabled()) return null;
  const raw = process.env.AISEARCH_API_BASE_URL?.trim();
  if (!raw) return null;
  return validateOrigin(raw, 'AISEARCH_API_BASE_URL', true);
}

export function getPublicSiteOrigin(): string {
  const raw = process.env.AISEARCH_PUBLIC_SITE_ORIGIN?.trim() || 'https://aisearcharab.com';
  return validateOrigin(raw, 'AISEARCH_PUBLIC_SITE_ORIGIN', true);
}
