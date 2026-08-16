(() => {
  "use strict";

  if (!("serviceWorker" in navigator)) return;
  if (location.protocol !== "https:" && location.hostname !== "localhost") return;

  const script = document.currentScript || document.querySelector('script[src$="/js/pwa-register.js"]');
  if (!script || !script.src) return;

  const scriptUrl = new URL(script.src, document.baseURI);
  if (scriptUrl.origin !== location.origin) return;

  const scopeUrl = new URL("../", scriptUrl);
  const workerUrl = new URL("sw.js", scopeUrl);

  navigator.serviceWorker.register(workerUrl.href, { scope: scopeUrl.pathname }).catch((error) => {
    console.warn("Service worker registration failed", error);
  });
})();
