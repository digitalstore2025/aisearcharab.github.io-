"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  user: null,
  generatedAnswersEnabled: false,
  answerController: null,
  sessionEpoch: 0,
  apiPrefix: null,
  publicSiteOrigin: null,
};

function readCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return "";
}

function csrfToken() {
  return readCookie("__Host-ais-csrf") || readCookie("ais_admin_csrf");
}

function apiPath(path) {
  if (!state.apiPrefix) throw new Error("assistant config unavailable");
  return `${state.apiPrefix}${path}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  let payload = null;
  if (response.status !== 204 && (response.headers.get("content-type") || "").includes("application/json")) {
    payload = await response.json();
  }
  if (!response.ok) {
    const error = new Error(payload?.detail || `Request failed (${response.status})`);
    error.status = response.status;
    error.retryAfter = response.headers.get("retry-after");
    throw error;
  }
  return payload;
}

function setStatus(text, kind = "neutral") {
  $("status-text").textContent = text;
  $("status-dot").dataset.kind = kind;
}

function cancelAnswerRequest() {
  if (state.answerController) {
    state.answerController.abort();
    state.answerController = null;
  }
}

function showAuthenticated(user) {
  cancelAnswerRequest();
  state.sessionEpoch += 1;
  state.user = user;
  $("login-panel").hidden = true;
  $("assistant-panel").hidden = false;
  $("identity").textContent = `${user.display_name} — ${user.role}`;
  setStatus(
    state.generatedAnswersEnabled
      ? "الجلسة صالحة وخدمة الإجابات الموثّقة متاحة."
      : "الجلسة صالحة، لكن خدمة الإجابات الموثّقة معطلة في هذه البيئة.",
    state.generatedAnswersEnabled ? "ok" : "warn",
  );
}

function showLoggedOut(message = "سجّل الدخول لاستخدام المساعد البحثي.") {
  cancelAnswerRequest();
  state.sessionEpoch += 1;
  state.user = null;
  $("assistant-panel").hidden = true;
  $("result-panel").hidden = true;
  $("login-panel").hidden = false;
  setStatus(message, "neutral");
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function safeExternalUrl(raw, base = window.location.origin) {
  try {
    const parsed = new URL(raw, base);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") return parsed.href;
  } catch (_error) {
    return null;
  }
  return null;
}

function addLink(parent, href, label, base) {
  const safe = safeExternalUrl(href, base);
  if (!safe) return;
  const link = document.createElement("a");
  link.href = safe;
  link.textContent = label;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  parent.appendChild(link);
}

function renderResult(result) {
  $("answer").textContent = result.answer;
  $("uncertainty").textContent = `عدم اليقين: ${result.uncertainty}`;
  $("uncertainty").dataset.level = result.uncertainty;
  $("model").textContent = `النموذج: ${result.model}`;
  $("usage").textContent = `Tokens: ${result.usage.total_tokens}`;
  $("request-id").textContent = `Request ID: ${result.request_id}`;

  const citations = $("citations");
  clearNode(citations);
  for (const citation of result.citations) {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = `${citation.evidence_id} — ${citation.title}`;
    item.appendChild(title);
    const internal = document.createElement("div");
    addLink(internal, citation.url, "فتح المادة", state.publicSiteOrigin);
    item.appendChild(internal);
    if (Array.isArray(citation.source_urls) && citation.source_urls.length) {
      const sources = document.createElement("div");
      sources.className = "source-links";
      citation.source_urls.forEach((url, index) => addLink(sources, url, `المصدر ${index + 1}`));
      item.appendChild(sources);
    }
    citations.appendChild(item);
  }

  const limitations = $("limitations");
  clearNode(limitations);
  for (const limitation of result.limitations || []) {
    const item = document.createElement("li");
    item.textContent = limitation;
    limitations.appendChild(item);
  }
  $("result-panel").hidden = false;
}

async function loadClientConfig() {
  const config = await api("/assistant/config.json");
  if (typeof config?.api_prefix !== "string" || !config.api_prefix.startsWith("/")) throw new Error("invalid api prefix");
  const publicOrigin = safeExternalUrl(config.public_site_origin);
  if (!publicOrigin || !publicOrigin.startsWith("https://")) throw new Error("invalid public site origin");
  state.apiPrefix = config.api_prefix.replace(/\/$/, "");
  state.publicSiteOrigin = publicOrigin;
}

async function routeMfaIfRequired() {
  const csrf = csrfToken();
  if (!csrf) return false;
  try {
    const mfa = await api(apiPath("/auth/mfa/status"), { headers: { "X-CSRF-Token": csrf } });
    if (mfa.required && !mfa.verified) {
      window.location.assign("/admin/");
      return true;
    }
  } catch (error) {
    if (error.status !== 401) throw error;
  }
  return false;
}

async function bootstrap() {
  try {
    await loadClientConfig();
  } catch (_error) {
    setStatus("تعذر تحميل إعدادات التطبيق بأمان.", "warn");
    return;
  }
  try {
    const capabilities = await api(apiPath("/meta/capabilities"));
    state.generatedAnswersEnabled = Boolean(capabilities.generated_answers);
  } catch (_error) {
    setStatus("تعذر قراءة قدرات الخدمة.", "warn");
  }
  try {
    if (await routeMfaIfRequired()) return;
    const user = await api(apiPath("/auth/me"));
    showAuthenticated(user);
  } catch (error) {
    if (error.status === 401) showLoggedOut();
    else setStatus("تعذر التحقق من الجلسة.", "warn");
  }
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("login-error").textContent = "";
  const button = event.currentTarget.querySelector("button[type='submit']");
  button.disabled = true;
  try {
    await api(apiPath("/auth/login"), {
      method: "POST",
      body: JSON.stringify({ email: $("email").value.trim(), password: $("password").value }),
    });
    $("password").value = "";
    if (await routeMfaIfRequired()) return;
    const user = await api(apiPath("/auth/me"));
    showAuthenticated(user);
  } catch (error) {
    $("login-error").textContent = error.status === 401 ? "بيانات الدخول غير صحيحة." : "تعذر تسجيل الدخول الآن.";
  } finally {
    button.disabled = false;
  }
});

$("logout-button").addEventListener("click", async () => {
  cancelAnswerRequest();
  const csrf = csrfToken();
  try {
    await api(apiPath("/auth/logout"), {
      method: "POST",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
    showLoggedOut("تم تسجيل الخروج.");
  } catch (error) {
    if (error.status === 401) {
      showLoggedOut("انتهت الجلسة.");
      return;
    }
    setStatus("تعذر تأكيد تسجيل الخروج. ما تزال الجلسة فعالة؛ أعد المحاولة.", "warn");
  }
});

$("question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("question-error").textContent = "";
  $("result-panel").hidden = true;
  const button = $("ask-button");
  button.disabled = true;
  button.textContent = "جارٍ التحقق من الأدلة…";
  cancelAnswerRequest();
  const controller = new AbortController();
  state.answerController = controller;
  const requestEpoch = state.sessionEpoch;

  try {
    if (!state.generatedAnswersEnabled) throw Object.assign(new Error("generated answers disabled"), { status: 503 });
    const csrf = csrfToken();
    if (!csrf) throw Object.assign(new Error("missing csrf"), { status: 401 });
    const result = await api(apiPath("/answers/grounded"), {
      method: "POST",
      signal: controller.signal,
      headers: { "X-CSRF-Token": csrf },
      body: JSON.stringify({
        query: $("query").value.trim(),
        max_sources: Number.parseInt($("max-sources").value, 10),
      }),
    });
    if (controller.signal.aborted || requestEpoch !== state.sessionEpoch || !state.user) return;
    renderResult(result);
  } catch (error) {
    if (error.name === "AbortError" || requestEpoch !== state.sessionEpoch) return;
    if (error.status === 401 || error.status === 403) {
      showLoggedOut("انتهت الجلسة أو لا تملك الصلاحية المطلوبة.");
    } else if (error.status === 422) {
      $("question-error").textContent = "الأدلة المنشورة غير كافية لهذا السؤال.";
    } else if (error.status === 429) {
      const suffix = error.retryAfter ? ` حاول مجددًا بعد ${error.retryAfter} ثانية.` : "";
      $("question-error").textContent = `تم بلوغ حد الاستخدام.${suffix}`;
    } else if (error.status === 409) {
      $("question-error").textContent = "تغيّرت الأدلة أثناء إنشاء الإجابة. أعد المحاولة.";
    } else if (error.status === 503) {
      $("question-error").textContent = "خدمة الإجابات غير متاحة حاليًا.";
    } else {
      $("question-error").textContent = "تعذر إنشاء إجابة موثّقة. لم يتم عرض ناتج غير متحقق.";
    }
  } finally {
    if (state.answerController === controller) state.answerController = null;
    button.disabled = false;
    button.textContent = "إنشاء إجابة موثّقة";
  }
});

bootstrap();
