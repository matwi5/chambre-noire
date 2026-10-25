// Service worker de l'application installée : ne touche qu'à l'ouverture des pages (jamais à /api/*), affiche
// une page d'explication quand l'ordinateur ne répond pas (éteint, en veille, ou téléphone hors de Tailscale), et
// affiche les notifications de fin de génération envoyées par l'ordinateur (Web Push).
const OFFLINE = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Chambre noire</title>
<meta name="theme-color" content="#0d0a08">
<style>body{margin:0;min-height:100dvh;display:grid;place-items:center;color:#f1e6d2;text-align:center;padding:24px;
background:radial-gradient(90% 55% at 50% -8%,rgba(190,28,18,.22),transparent 72%) #0d0a08;
font:16px/1.5 system-ui,sans-serif}p{color:rgba(241,230,210,.68);max-width:320px}
button{margin-top:12px;height:44px;padding:0 22px;border:0;border-radius:6px;background:#ffa53a;
color:#1c1006;font:inherit;font-weight:700}</style>
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
    await self.registration.showNotification(d.title || "Chambre noire", {
      body: d.body || "", tag: d.tag || "qwen-image-job", icon: "/icon-192.png", badge: "/icon-192.png",
      data: { url: d.url || "/" } });
  })());
});

// toucher la notification : le Labo, sur la pile, devant l'image terminée. Application déjà ouverte : sa fenêtre est
// ramenée et la page passe au Labo (message « go », sans recharger : la page garde ses générations suivies) ; sinon
// elle s'ouvre à l'adresse de la notification, qui arrive sur le Labo
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const win = wins.find((w) => w.focused) || wins[0];
    if (!win) return self.clients.openWindow(e.notification.data && e.notification.data.url || "/");
    win.postMessage({ go: "labo" });
    await win.focus().catch(() => {});   // refusé par le navigateur : la page est quand même passée au Labo
  })());
});
