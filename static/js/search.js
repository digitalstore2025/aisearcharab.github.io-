(() => {
  'use strict';

  const form = document.querySelector('#search-form');
  const input = document.querySelector('#search-input');
  const status = document.querySelector('#search-status');
  const results = document.querySelector('#search-results');
  if (!form || !input || !status || !results) return;

  const normalizeArabic = (value = '') => value
    .normalize('NFKD')
    .replace(/[\u064B-\u065F\u0670\u06D6-\u06ED]/g, '')
    .replace(/\u0640/g, '')
    .replace(/[إأآٱ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ؤ/g, 'و')
    .replace(/ئ/g, 'ي')
    .toLocaleLowerCase('ar')
    .trim();

  const safeText = (value) => typeof value === 'string' ? value : '';
  const meta = document.querySelector('meta[name="aisearcharab-api-base"]');
  let apiBase = '';
  try {
    if (meta && meta.content) {
      const candidate = new URL(meta.content, window.location.origin);
      const localHttp = candidate.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(candidate.hostname);
      if (candidate.protocol === 'https:' || localHttp) apiBase = candidate.href.replace(/\/$/, '');
    }
  } catch (_) { apiBase = ''; }

  let searchIndex = [];
  let localReady = false;
  let timer;
  let requestSequence = 0;
  let activeController;

  const setStatus = (message) => { status.textContent = message; };
  const clearResults = () => { results.replaceChildren(); };

  const safeSiteUrl = (value) => {
    try {
      const candidate = new URL(safeText(value) || '/', window.location.origin);
      return candidate.origin === window.location.origin ? candidate.href : '/';
    } catch (_) { return '/'; }
  };

  const createResult = (item) => {
    const article = document.createElement('article');
    article.className = 'search-result';
    const heading = document.createElement('h2');
    const link = document.createElement('a');
    link.href = safeSiteUrl(item.url);
    link.textContent = safeText(item.title) || 'مادة بلا عنوان';
    heading.append(link);
    const summary = document.createElement('p');
    summary.textContent = safeText(item.summary) || 'لا يتوفر ملخص لهذه المادة.';
    const metaLine = document.createElement('p');
    metaLine.className = 'meta';
    const section = safeText(item.section) || 'محتوى';
    const date = safeText(item.date || item.published_at).slice(0, 10);
    metaLine.textContent = date ? `${section} · ${date}` : section;
    article.append(heading, summary, metaLine);
    return article;
  };

  const render = (items, sourceLabel) => {
    clearResults();
    if (!items.length) {
      setStatus('لم نعثر على نتائج مطابقة. جرّب عبارة أقصر أو صياغة مختلفة.');
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = 'لا توجد نتائج متاحة لهذا الاستعلام.';
      results.append(empty);
      return;
    }
    setStatus(`عدد النتائج: ${items.length} · ${sourceLabel}`);
    const fragment = document.createDocumentFragment();
    items.forEach((item) => fragment.append(createResult(item)));
    results.append(fragment);
  };

  const scoreItem = (item, terms) => {
    const title = normalizeArabic(safeText(item.title));
    const summary = normalizeArabic(safeText(item.summary));
    const section = normalizeArabic(safeText(item.section));
    const haystack = `${title} ${summary} ${section}`;
    if (!terms.every((term) => haystack.includes(term))) return -1;
    return terms.reduce((score, term) => {
      if (title.includes(term)) score += 5;
      if (section.includes(term)) score += 2;
      if (summary.includes(term)) score += 1;
      return score;
    }, 0);
  };

  const localSearch = (query) => {
    if (!localReady) return null;
    const terms = query.split(/\s+/).filter(Boolean);
    return searchIndex
      .map((item) => ({ item, score: scoreItem(item, terms) }))
      .filter(({ score }) => score >= 0)
      .sort((a, b) => b.score - a.score || safeText(b.item.date).localeCompare(safeText(a.item.date)))
      .slice(0, 24)
      .map(({ item }) => item);
  };

  const remoteSearch = async (rawQuery) => {
    if (!apiBase) throw new Error('remote search is not configured');
    if (activeController) activeController.abort();
    activeController = new AbortController();
    const timeout = window.setTimeout(() => activeController.abort(), 4500);
    try {
      const url = new URL(`${apiBase}/v1/search`);
      url.searchParams.set('q', rawQuery);
      url.searchParams.set('limit', '24');
      const response = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        credentials: 'omit',
        cache: 'no-store',
        signal: activeController.signal
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      return Array.isArray(payload.results) ? payload.results : [];
    } finally { window.clearTimeout(timeout); }
  };

  const runSearch = async () => {
    const sequence = ++requestSequence;
    const rawQuery = input.value.slice(0, 120);
    const query = normalizeArabic(rawQuery);
    clearResults();
    const url = new URL(window.location.href);
    if (rawQuery.trim()) url.searchParams.set('q', rawQuery.trim()); else url.searchParams.delete('q');
    window.history.replaceState({}, '', url);
    if (query.length < 2) { setStatus('اكتب حرفين على الأقل لبدء البحث.'); return; }

    if (apiBase) {
      setStatus('يجري البحث في الفهرس المحكوم…');
      try {
        const remote = await remoteSearch(rawQuery.trim());
        if (sequence !== requestSequence) return;
        render(remote, 'الفهرس المركزي');
        return;
      } catch (_) {
        if (sequence !== requestSequence) return;
      }
    }

    const local = localSearch(query);
    if (local === null) { setStatus('يجري تحميل الفهرس المحلي…'); return; }
    render(local, apiBase ? 'نسخة محلية احتياطية' : 'الفهرس المحلي');
  };

  fetch('/index.json', { credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-cache' })
    .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then((data) => { searchIndex = Array.isArray(data) ? data.filter((item) => item && typeof item === 'object') : []; localReady = true; runSearch(); })
    .catch(() => { localReady = false; if (!apiBase) setStatus('تعذر تحميل فهرس البحث حالياً. أعد المحاولة لاحقاً.'); });

  const initialQuery = new URLSearchParams(window.location.search).get('q');
  if (initialQuery) input.value = initialQuery.slice(0, 120);
  input.addEventListener('input', () => { window.clearTimeout(timer); timer = window.setTimeout(runSearch, 180); });
  form.addEventListener('submit', (event) => { event.preventDefault(); runSearch(); });
})();
