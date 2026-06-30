const CACHE_NAME = "weather-risk-assistant-v2";
const APP_SHELL = [
  "/",
  "/static/mobile.html",
  "/static/mobile.js",
  "/static/manifest.webmanifest",
  "/static/assets/app/icon-192.png",
  "/static/assets/app/icon-512.png",
  "/static/assets/weather/clear-cn.png",
  "/static/assets/weather/cloudy-cn.png",
  "/static/assets/weather/rain-cn.png",
  "/static/assets/weather/thunder-cn.png",
  "/static/assets/weather/wind-cn.png",
  "/static/assets/weather/heat-cn.png",
  "/static/assets/weather/fog-cn.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match("/static/mobile.html")))
  );
});
