(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const loginPanel = $('#login-panel');
  const appPanel = $('#app-panel');
  const sessionTools = $('#session-tools');
  const statusBox = $('#global-status');
  let currentUser = null;
  let selectedContent = null;

  const csrfToken = () => {
    const names = ['__Host-ais-csrf', 'ais_admin_csrf'];
    for (const part of document.cookie.split(';')) {
      const [rawName, ...rest] = part.trim().split('=');
      if (names.includes(rawName)) return decodeURIComponent(rest.join('='));
    }
    return '';
  };

  const api = async (path, options = {}) => {
    const method = (options.method || 'GET').toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    if (options.body) headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRF-Token', csrfToken());
    const response = await fetch(`/v1${path}`, { ...options, method, headers, credentials: 'same-origin' });
    if (response.status === 204) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  };

  const setStatus = (message, type = '') => {
    if (!statusBox) return;
    statusBox.textContent = message;
    statusBox.className = type ? `message-${type}` : '';
  };

  const clear = (node) => node.replaceChildren();
  const can = (permission) => currentUser && currentUser.permissions.includes(permission);
  const make = (tag, text, className = '') => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  const showLogin = () => {
    currentUser = null;
    selectedContent = null;
    loginPanel.hidden = false;
    appPanel.hidden = true;
    sessionTools.hidden = true;
  };

  const showApp = (user) => {
    currentUser = user;
    loginPanel.hidden = true;
    appPanel.hidden = false;
    sessionTools.hidden = false;
    $('#current-user').textContent = `${user.display_name} — ${user.role}`;
    document.querySelectorAll('[data-permission]').forEach((node) => {
      node.hidden = !can(node.dataset.permission);
    });
  };

  const renderContent = (items) => {
    const list = $('#content-list');
    clear(list);
    if (!items.length) { list.append(make('p', 'لا توجد مواد بعد.', 'meta')); return; }
    items.forEach((item) => {
      const card = make('article', undefined, 'card');
      card.append(make('h3', item.title));
      card.append(make('p', `${item.section} · ${item.status} · مصادر ${item.source_count} · ادعاءات ${item.claim_count}`, 'meta'));
      const actions = make('div', undefined, 'actions');
      const selectButton = make('button', 'فتح', 'secondary');
      selectButton.type = 'button';
      selectButton.addEventListener('click', () => selectContent(item.id));
      actions.append(selectButton);
      card.append(actions);
      list.append(card);
    });
  };

  const renderSelected = (item) => {
    selectedContent = item;
    $('#selected-panel').hidden = false;
    $('#selected-title').textContent = item.title;
    $('#selected-status').textContent = item.status;
    $('#selected-summary').textContent = item.summary;
    const actions = $('#workflow-actions');
    clear(actions);
    const addAction = (label, target, permission, className = '') => {
      if (!can(permission)) return;
      const button = make('button', label, className);
      button.type = 'button';
      button.addEventListener('click', () => transitionContent(target));
      actions.append(button);
    };
    if (item.status === 'draft') addAction('إرسال للمراجعة', 'reviewed', 'content:review');
    if (item.status === 'reviewed') {
      addAction('إعادة لمسودة', 'draft', 'content:write', 'secondary');
      addAction('نشر', 'published', 'content:publish');
    }
    if (item.status === 'published') addAction('أرشفة', 'archived', 'content:publish', 'danger');
    if (item.status === 'archived') addAction('إعادة لمسودة', 'draft', 'content:write');

    const sources = $('#source-list'); clear(sources);
    item.sources.forEach((source) => {
      const row = make('div', undefined, 'item');
      row.append(make('strong', source.title));
      row.append(make('div', `${source.publisher} · ${source.reliability}`, 'meta'));
      sources.append(row);
    });
    if (!item.sources.length) sources.append(make('p', 'لا توجد مصادر.', 'meta'));

    const claims = $('#claim-list'); clear(claims);
    item.claims.forEach((claim) => {
      const row = make('div', undefined, 'item');
      row.append(make('strong', claim.text));
      row.append(make('div', `${claim.claim_type} · ${claim.confidence} · ${claim.review_status}`, 'meta'));
      if (can('claims:review') && claim.id) {
        const claimActions = make('div', undefined, 'actions');
        [['مراجَع','reviewed'],['منشور','published'],['مرفوض','rejected']].forEach(([label, state]) => {
          const button = make('button', label, state === 'rejected' ? 'danger' : 'secondary');
          button.type = 'button';
          button.addEventListener('click', () => reviewClaim(claim.id, state, claim.confidence === 'unverified' ? 'medium' : claim.confidence));
          claimActions.append(button);
        });
        row.append(claimActions);
      }
      claims.append(row);
    });
    if (!item.claims.length) claims.append(make('p', 'لا توجد ادعاءات منظمة.', 'meta'));
  };

  const renderUsers = (users) => {
    const list = $('#user-list'); clear(list);
    users.forEach((user) => {
      const row = make('div', undefined, 'item');
      row.append(make('strong', user.display_name));
      row.append(make('div', `${user.email} · ${user.role} · ${user.is_active ? 'نشط' : 'معطل'}`, 'meta'));
      list.append(row);
    });
  };

  const renderAudit = (events) => {
    const list = $('#audit-list'); clear(list);
    events.forEach((event) => {
      const row = make('div', undefined, 'item');
      row.append(make('strong', `${event.action} — ${event.outcome}`));
      row.append(make('div', `${event.target_type || '—'} · ${event.target_id || '—'} · ${new Date(event.created_at).toLocaleString('ar')}`, 'meta'));
      list.append(row);
    });
  };

  const loadContent = async () => renderContent(await api('/admin/content'));
  const loadUsers = async () => { if (can('users:read')) renderUsers(await api('/admin/users')); };
  const loadAudit = async () => { if (can('audit:read')) renderAudit(await api('/admin/audit')); };
  const selectContent = async (id) => renderSelected(await api(`/admin/content/${encodeURIComponent(id)}`));

  const loadApplication = async () => {
    try {
      const user = await api('/auth/me');
      showApp(user);
      await Promise.all([loadContent(), loadUsers(), loadAudit()]);
      setStatus('تم تحميل البيانات.', 'success');
    } catch (error) {
      if (error.status === 401) showLogin();
      else setStatus(error.message, 'error');
    }
  };

  const transitionContent = async (target) => {
    if (!selectedContent) return;
    try {
      const item = await api(`/admin/content/${selectedContent.id}/transition`, { method: 'POST', body: JSON.stringify({ status: target }) });
      renderSelected(item); await loadContent(); setStatus('تم تحديث حالة المادة.', 'success');
    } catch (error) { setStatus(error.message, 'error'); }
  };

  const reviewClaim = async (claimId, reviewStatus, confidence) => {
    try {
      await api(`/admin/claims/${claimId}`, { method: 'PATCH', body: JSON.stringify({ review_status: reviewStatus, confidence }) });
      await selectContent(selectedContent.id); setStatus('تم تحديث مراجعة الادعاء.', 'success');
    } catch (error) { setStatus(error.message, 'error'); }
  };

  $('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email: $('#login-email').value, password: $('#login-password').value }) });
      $('#login-password').value = '';
      showApp(payload.user);
      await Promise.all([loadContent(), loadUsers(), loadAudit()]);
      setStatus('تم تسجيل الدخول.', 'success');
    } catch (error) {
      const message = make('p', error.message, 'message-error');
      loginPanel.querySelectorAll('.message-error').forEach((node) => node.remove());
      loginPanel.append(message);
    }
  });

  $('#logout-button').addEventListener('click', async () => {
    try { await api('/auth/logout', { method: 'POST' }); } finally { showLogin(); }
  });
  $('#refresh-content').addEventListener('click', () => loadContent().catch((error) => setStatus(error.message, 'error')));
  $('#refresh-users').addEventListener('click', () => loadUsers().catch((error) => setStatus(error.message, 'error')));
  $('#refresh-audit').addEventListener('click', () => loadAudit().catch((error) => setStatus(error.message, 'error')));

  $('#content-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = {
      title: $('#content-title').value,
      slug: $('#content-slug').value,
      url_path: $('#content-url').value,
      section: $('#content-section').value,
      language: $('#content-language').value,
      source_authority: Number($('#content-authority').value),
      summary: $('#content-summary').value,
      body: $('#content-body').value
    };
    try {
      const item = await api('/admin/content', { method: 'POST', body: JSON.stringify(payload) });
      event.target.reset(); $('#content-url').value = '/'; $('#content-section').value = 'news'; $('#content-language').value = 'ar';
      await loadContent(); renderSelected(item); setStatus('حُفظت المسودة.', 'success');
    } catch (error) { setStatus(error.message, 'error'); }
  });

  $('#user-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = { display_name: $('#user-name').value, email: $('#user-email').value, role: $('#user-role').value, password: $('#user-password').value };
    try {
      await api('/admin/users', { method: 'POST', body: JSON.stringify(payload) });
      event.target.reset(); await loadUsers(); setStatus('تم إنشاء المستخدم.', 'success');
    } catch (error) { setStatus(error.message, 'error'); }
  });

  $('#source-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (!selectedContent) return;
    const payload = { source_key: $('#source-key').value, title: $('#source-title').value, publisher: $('#source-publisher').value, url: $('#source-url').value, source_type: $('#source-type').value, language: 'ar', reliability: $('#source-reliability').value };
    try { const item = await api(`/admin/content/${selectedContent.id}/sources`, { method: 'POST', body: JSON.stringify(payload) }); event.target.reset(); renderSelected(item); await loadContent(); setStatus('تم إرفاق المصدر.', 'success'); } catch (error) { setStatus(error.message, 'error'); }
  });

  $('#claim-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (!selectedContent) return;
    const payload = { claim_key: $('#claim-key').value, text: $('#claim-text').value, claim_type: $('#claim-type').value, confidence: $('#claim-confidence').value };
    try { const item = await api(`/admin/content/${selectedContent.id}/claims`, { method: 'POST', body: JSON.stringify(payload) }); event.target.reset(); renderSelected(item); await loadContent(); setStatus('تمت إضافة الادعاء.', 'success'); } catch (error) { setStatus(error.message, 'error'); }
  });

  loadApplication();
})();
