const CACHE_VERSION = "aisearcharab-pwa-v4";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const SCOPE_URL = new URL(self.registration.scope);
const SCOPE_PATH = SCOPE_URL.pathname.endsWith("/") ? SCOPE_URL.pathname : `${SCOPE_URL.pathname}/`;
const MAX_RUNTIME_ENTRIES = 80;

const scopeUrl = (path = "") => new URL(path.replace(/^\/+/, ""), SCOPE_URL).href;
const OFFLINE_URL = scopeUrl("offline.html");

const PRECACHE_URLS = [
  scopeUrl(),
  OFFLINE_URL,
  scopeUrl("site.webmanifest"),
  scopeUrl("favicon.svg"),
  scopeUrl("icons/icon-192.png"),
  scopeUrl("icons/icon-512.png"),
  scopeUrl("css/main.css"),
  scopeUrl("css/article.css"),
  scopeUrl("js/pwa-register.js")
];

const SENSITIVE_PREFIXES = ["/api/", "/v1/", "/admin", "/health/"];
const SENSITIVE_EXACT = new Set(["/docs", "/docs/", "/openapi.json", "/index.json"]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith("aisearcharab-pwa-") && ![STATIC_CACHE, RUNTIME_CACHE].includes(key))
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

function relativePath(url) {
  if (!url.pathname.startsWith(SCOPE_PATH)) return null;
  const relative = url.pathname.slice(SCOPE_PATH.length);
  return `/${relative}`;
}

function isSensitivePath(path) {
  if (path === null) return true;
  return SENSITIVE_EXACT.has(path) || SENSITIVE_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function isCacheableResponse(response) {
  if (!response || !response.ok || response.type === "opaque") return false;
  const cacheControl = response.headers.get("Cache-Control") || "";
  return !/no-store|private/i.test(cacheControl);
}

async function trimRuntimeCache(cache) {
  const keys = await cache.keys();
  const overflow = keys.length - MAX_RUNTIME_ENTRIES;
  if (overflow <= 0) return;
  await Promise.all(keys.slice(0, overflow).map((key) => cache.delete(key)));
}

async function cacheRuntimeResponse(cache, request, response) {
  if (!isCacheableResponse(response)) return;
  await cache.put(request, response.clone());
  await trimRuntimeCache(cache);
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    await cacheRuntimeResponse(cache, request, response);
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    const offline = await caches.match(OFFLINE_URL);
    return cached || offline || new Response("Offline", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" }
    });
  }
}

async function staleWhileRevalidate(request) {
  const runtimeCache = await caches.open(RUNTIME_CACHE);
  const cached = await caches.match(request);

  const networkPromise = fetch(request)
    .then(async (response) => {
      await cacheRuntimeResponse(runtimeCache, request, response);
      return response;
    })
    .catch(() => null);

  if (cached) {
    void networkPromise;
    return cached;
  }

  const network = await networkPromise;
  return network || new Response("Offline", {
    status: 503,
    headers: { "Content-Type": "text/plain; charset=utf-8" }
  });
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const path = relativePath(url);
  if (isSensitivePath(path)) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }

  if (["style", "script", "image", "font"].includes(request.destination)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
