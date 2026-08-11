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
  let searchIndex = [];
  let ready = false;
  let timer;

  const setStatus = (message) => { status.textContent = message; };
  const clearResults = () => { results.replaceChildren(); };

  const createResult = (item) => {
    const article = document.createElement('article');
    article.className = 'search-result';

    const heading = document.createElement('h2');
    const link = document.createElement('a');
    const candidate = new URL(safeText(item.url) || '/', window.location.origin);
    link.href = candidate.origin === window.location.origin ? candidate.href : '/';
    link.textContent = safeText(item.title) || 'مادة بلا عنوان';
    heading.append(link);

    const summary = document.createElement('p');
    summary.textContent = safeText(item.summary) || 'لا يتوفر ملخص لهذه المادة.';

    const meta = document.createElement('p');
    meta.className = 'meta';
    const section = safeText(item.section) || 'محتوى';
    const date = safeText(item.date);
    meta.textContent = date ? `${section} · ${date}` : section;

    article.append(heading, summary, meta);
    return article;
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

  const runSearch = () => {
    const rawQuery = input.value.slice(0, 120);
    const query = normalizeArabic(rawQuery);
    clearResults();

    const url = new URL(window.location.href);
    if (rawQuery.trim()) url.searchParams.set('q', rawQuery.trim());
    else url.searchParams.delete('q');
    window.history.replaceState({}, '', url);

    if (query.length < 2) {
      setStatus('اكتب حرفين على الأقل لبدء البحث.');
      return;
    }
    if (!ready) {
      setStatus('يجري تحميل فهرس البحث…');
      return;
    }

    const terms = query.split(/\s+/).filter(Boolean);
    const matches = searchIndex
      .map((item) => ({ item, score: scoreItem(item, terms) }))
      .filter(({ score }) => score >= 0)
      .sort((a, b) => b.score - a.score || safeText(b.item.date).localeCompare(safeText(a.item.date)))
      .slice(0, 24);

    if (!matches.length) {
      setStatus('لم نعثر على نتائج مطابقة. جرّب عبارة أقصر أو صياغة مختلفة.');
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = 'لا توجد نتائج متاحة لهذا الاستعلام.';
      results.append(empty);
      return;
    }

    setStatus(`عدد النتائج: ${matches.length}`);
    const fragment = document.createDocumentFragment();
    matches.forEach(({ item }) => fragment.append(createResult(item)));
    results.append(fragment);
  };

  fetch('/index.json', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    cache: 'no-cache'
  })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      searchIndex = Array.isArray(data) ? data.filter((item) => item && typeof item === 'object') : [];
      ready = true;
      runSearch();
    })
    .catch(() => {
      ready = false;
      clearResults();
      setStatus('تعذر تحميل فهرس البحث حالياً. أعد المحاولة لاحقاً.');
    });

  const initialQuery = new URLSearchParams(window.location.search).get('q');
  if (initialQuery) input.value = initialQuery.slice(0, 120);

  input.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(runSearch, 120);
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    runSearch();
  });
})();
