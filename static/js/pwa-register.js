(() => {
  if (!("serviceWorker" in navigator)) return;
  if (location.protocol !== "https:" && location.hostname !== "localhost") return;

  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((error) => {
    console.warn("Service worker registration failed", error);
  });
})();
