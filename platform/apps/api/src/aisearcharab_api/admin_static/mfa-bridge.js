(() => {
  'use strict';

  const originalFetch = window.fetch.bind(window);
  const configPromise = originalFetch('/assistant/config.json', {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  }).then(async (response) => {
    if (!response.ok) throw new Error('runtime config unavailable');
    const config = await response.json();
    if (typeof config.api_prefix !== 'string' || !config.api_prefix.startsWith('/')) {
      throw new Error('invalid api prefix');
    }
    return config.api_prefix.replace(/\/$/, '');
  });

  const csrfToken = () => {
    const names = ['__Host-ais-csrf', 'ais_admin_csrf'];
    for (const part of document.cookie.split(';')) {
      const [rawName, ...rest] = part.trim().split('=');
      if (names.includes(rawName)) return decodeURIComponent(rest.join('='));
    }
    return '';
  };

  const directApi = async (path, options = {}) => {
    const apiPrefix = await configPromise;
    const method = (options.method || 'GET').toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    headers.set('X-CSRF-Token', csrfToken());
    if (options.body) headers.set('Content-Type', 'application/json');
    const response = await originalFetch(`${apiPrefix}${path}`, {
      ...options,
      method,
      headers,
      credentials: 'same-origin'
    });
    if (response.status === 204) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  };

  const node = (tag, text) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    return element;
  };

  const closeDialog = (dialog) => {
    if (dialog.open) dialog.close();
    dialog.remove();
  };

  const codeDialog = ({ titleText, helpText, submitText = 'تحقق' }) => new Promise((resolve, reject) => {
    const dialog = document.createElement('dialog');
    const form = document.createElement('form');
    form.method = 'dialog';
    const title = node('h2', titleText);
    const help = node('p', helpText);
    const label = node('label', 'رمز التحقق');
    const input = document.createElement('input');
    input.type = 'text';
    input.inputMode = 'numeric';
    input.autocomplete = 'one-time-code';
    input.dir = 'ltr';
    input.required = true;
    input.minLength = 6;
    input.maxLength = 64;
    label.append(input);
    const message = node('p', '');
    message.setAttribute('role', 'alert');
    const actions = document.createElement('div');
    actions.className = 'actions';
    const cancel = node('button', 'إلغاء');
    cancel.type = 'button';
    cancel.className = 'secondary';
    const submit = node('button', submitText);
    submit.type = 'submit';
    actions.append(cancel, submit);
    form.append(title, help, label, message, actions);
    dialog.append(form);
    document.body.append(dialog);

    cancel.addEventListener('click', () => {
      closeDialog(dialog);
      reject(new Error('تم إلغاء التحقق متعدد العوامل.'));
    });
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      closeDialog(dialog);
      reject(new Error('تم إلغاء التحقق متعدد العوامل.'));
    });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = input.value.trim();
      if (!value) return;
      submit.disabled = true;
      closeDialog(dialog);
      resolve(value);
    });
    dialog.showModal();
    input.focus();
  });

  const verifyExistingMfa = async () => {
    while (true) {
      const code = await codeDialog({
        titleText: 'التحقق متعدد العوامل',
        helpText: 'أدخل رمز تطبيق المصادقة المكوّن من 6 أرقام أو أحد أكواد الاسترداد أحادية الاستخدام.'
      });
      try {
        await directApi('/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) });
        return;
      } catch (error) {
        if (error.status === 401) {
          window.alert('رمز التحقق غير صالح أو استُخدم سابقًا.');
          continue;
        }
        throw error;
      }
    }
  };

  const showRecoveryCodes = (codes) => new Promise((resolve) => {
    const dialog = document.createElement('dialog');
    const title = node('h2', 'أكواد الاسترداد');
    const warning = node('p', 'احفظ هذه الأكواد الآن في مكان آمن. كل كود صالح للاستخدام مرة واحدة ولن تعرضه المنصة بهذه الصورة مرة أخرى.');
    const pre = node('pre', codes.join('\n'));
    pre.dir = 'ltr';
    pre.setAttribute('aria-label', 'أكواد الاسترداد');
    const acknowledgement = node('label', ' حفظت أكواد الاسترداد في مكان آمن');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    acknowledgement.prepend(checkbox);
    const done = node('button', 'متابعة إلى لوحة الإدارة');
    done.type = 'button';
    done.disabled = true;
    checkbox.addEventListener('change', () => { done.disabled = !checkbox.checked; });
    done.addEventListener('click', () => {
      closeDialog(dialog);
      resolve();
    });
    dialog.append(title, warning, pre, acknowledgement, done);
    document.body.append(dialog);
    dialog.addEventListener('cancel', (event) => event.preventDefault());
    dialog.showModal();
    checkbox.focus();
  });

  const enrollMfa = async (password) => {
    const started = await directApi('/auth/mfa/enroll/start', {
      method: 'POST',
      body: JSON.stringify({ password })
    });

    const dialog = document.createElement('dialog');
    const title = node('h2', 'تفعيل المصادقة متعددة العوامل');
    const intro = node('p', 'أضف الحساب إلى تطبيق مصادقة متوافق مع TOTP باستخدام المفتاح التالي. لا تحفظه داخل المتصفح.');
    const secretLabel = node('p', 'مفتاح الإعداد:');
    const secret = node('code', started.secret);
    secret.dir = 'ltr';
    const uriLabel = node('p', 'رابط otpauth للتطبيقات المتوافقة:');
    const uri = node('code', started.otpauth_uri);
    uri.dir = 'ltr';
    const proceed = node('button', 'أدخل رمز التحقق');
    proceed.type = 'button';
    dialog.append(title, intro, secretLabel, secret, uriLabel, uri, proceed);
    document.body.append(dialog);

    await new Promise((resolve, reject) => {
      proceed.addEventListener('click', resolve, { once: true });
      dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        closeDialog(dialog);
        reject(new Error('تم إلغاء إعداد المصادقة متعددة العوامل.'));
      });
      dialog.showModal();
      proceed.focus();
    });
    closeDialog(dialog);

    while (true) {
      const code = await codeDialog({
        titleText: 'تأكيد تطبيق المصادقة',
        helpText: 'أدخل الرمز الحالي من تطبيق المصادقة لإكمال التسجيل.',
        submitText: 'تفعيل MFA'
      });
      try {
        const confirmed = await directApi('/auth/mfa/enroll/confirm', {
          method: 'POST',
          body: JSON.stringify({ code })
        });
        await showRecoveryCodes(confirmed.recovery_codes);
        return;
      } catch (error) {
        if (error.status === 401) {
          window.alert('الرمز غير صحيح. تحقق من وقت الجهاز وحاول مجددًا.');
          continue;
        }
        throw error;
      }
    }
  };

  const cancelPendingSession = async () => {
    try {
      await directApi('/auth/mfa/cancel-session', { method: 'POST' });
    } catch (_) {
      // Best-effort cleanup only; never expose internal failure details here.
    }
  };

  window.fetch = async (input, init = {}) => {
    const apiPrefix = await configPromise;
    const rawUrl = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
    const url = new URL(rawUrl, window.location.origin);
    const method = (init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const isLogin = method === 'POST' && url.origin === window.location.origin && url.pathname === `${apiPrefix}/auth/login`;
    const response = await originalFetch(input, init);
    if (!isLogin || !response.ok) return response;

    let password = '';
    try {
      if (typeof init.body === 'string') {
        const parsed = JSON.parse(init.body);
        password = typeof parsed.password === 'string' ? parsed.password : '';
      }
      const status = await directApi('/auth/mfa/status');
      if (!status.required || status.verified) return response;
      if (!status.enrolled) {
        if (!password) throw new Error('تعذر بدء إعداد المصادقة متعددة العوامل. أعد تسجيل الدخول.');
        await enrollMfa(password);
      } else {
        await verifyExistingMfa();
      }
      return response;
    } catch (error) {
      await cancelPendingSession();
      const detail = error instanceof Error ? error.message : 'تعذر إكمال المصادقة متعددة العوامل.';
      return new Response(JSON.stringify({ detail }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    } finally {
      password = '';
    }
  };
})();