(() => {
  const input = document.querySelector('#search-input');
  const results = document.querySelector('#search-results');
  if (!input || !results) return;

  let index = [];
  fetch('/index.json')
    .then((response) => {
      if (!response.ok) throw new Error('Search index unavailable');
      return response.json();
    })
    .then((data) => { index = Array.isArray(data) ? data : []; })
    .catch(() => { results.textContent = 'تعذر تحميل فهرس البحث.'; });

  input.addEventListener('input', () => {
    const query = input.value.trim().toLocaleLowerCase('ar');
    results.replaceChildren();
    if (query.length < 2) return;

    const matches = index.filter((item) => {
      const haystack = `${item.title} ${item.summary} ${item.section}`.toLocaleLowerCase('ar');
      return haystack.includes(query);
    }).slice(0, 20);

    if (!matches.length) {
      results.textContent = 'لا توجد نتائج مطابقة.';
      return;
    }

    for (const item of matches) {
      const article = document.createElement('article');
      article.className = 'card';
      const title = document.createElement('h2');
      const link = document.createElement('a');
      link.href = item.url;
      link.textContent = item.title;
      title.append(link);
      const summary = document.createElement('p');
      summary.textContent = item.summary;
      article.append(title, summary);
      results.append(article);
    }
  });
})();
