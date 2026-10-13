// Service worker de l'application installée : ne touche qu'à l'ouverture des pages (jamais à /api/*), affiche
// une page d'explication quand l'ordinateur ne répond pas (éteint, en veille, ou téléphone hors de Tailscale), et
// affiche les notifications de fin de génération envoyées par l'ordinateur (Web Push).
const OFFLINE = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Qwen-Image</title>
<style>body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#0b0a16;color:#f6f4ff;
font:16px/1.5 system-ui,sans-serif;text-align:center;padding:24px}p{color:rgba(236,233,255,.68);max-width:320px}
button{margin-top:12px;height:44px;padding:0 22px;border:0;border-radius:999px;background:#8f7cff;color:#fff;font:inherit;font-weight:600}</style>
</head><body><div><h1>Ordinateur injoignable</h1><p>Vérifiez qu'il est allumé, que l'interface tourne et que Tailscale
est connecté sur ce téléphone.</p><button onclick="location.reload()">Réessayer</button></div></body></html>`;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() =>
    new Response(OFFLINE, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } })));
});

self.addEventListener("push", (e) => {
  const d = e.data ? e.data.json() : {};
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    if (wins.some((w) => w.visibilityState === "visible")) return;   // application à l'écran : elle montre déjà l'image
    await self.registration.showNotification(d.title || "Qwen-Image", {
      body: d.body || "", tag: d.tag || "qwen-image-job", icon: "/icon-192.png", badge: "/icon-192.png",
      data: { url: d.url || "/" } });
  })());
});

self.addEventListener("notificationclick", (e) => {   // toucher la notification : ramène l'application, ou l'ouvre
  e.notification.close();
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    if (wins.length) return wins[0].focus();
    return self.clients.openWindow(e.notification.data && e.notification.data.url || "/");
  })());
});
