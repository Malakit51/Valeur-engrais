// Valeur des engrais : le service worker de l'appli installée. La page vient d'Internet quand il y a du réseau (donc
// toujours à jour), sinon de la copie gardée sur le téléphone : l'appli s'ouvre aussi au champ sans réseau. Les
// polices (Google Fonts) sont gardées à la première lecture. Il reçoit aussi les alertes du relevé du lundi
// (notifications Web Push envoyées par GitHub Actions, outils/releve.py) et les montre sur le téléphone.
const CACHE = "valeur-engrais-v4";
const FICHIERS = ["./", "index.html", "manifest.webmanifest", "icone.svg", "icone-192.png", "icone-512.png", "icone-apple.png"];

self.addEventListener("install", ev => {
  ev.waitUntil(caches.open(CACHE).then(c => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", ev => {
  ev.waitUntil(caches.keys()
    .then(cles => Promise.all(cles.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", ev => {
  const req = ev.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // les polices : la copie gardée d'abord
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    ev.respondWith(caches.match(req).then(r => r || fetch(req).then(rep => {
      const copie = rep.clone();
      caches.open(CACHE).then(c => c.put(req, copie));
      return rep;
    })));
    return;
  }
  if (url.origin !== location.origin) return;
  // la page et ses fichiers : Internet d'abord, la copie gardée sans réseau
  ev.respondWith(fetch(req).then(rep => {
    if (rep.ok) { const copie = rep.clone(); caches.open(CACHE).then(c => c.put(req, copie)); }
    return rep;
  }).catch(() => caches.match(req).then(r => r || caches.match("index.html"))));
});

// une alerte du relevé : {titre, texte, url}
self.addEventListener("push", ev => {
  let d = {};
  try { d = ev.data ? ev.data.json() : {}; } catch (e) { d = {texte: ev.data && ev.data.text()}; }
  ev.waitUntil(self.registration.showNotification(d.titre || "Valeur des engrais", {
    body: d.texte || "Un cours d'engrais est à regarder.", icon: "icone-192.png", badge: "icone-192.png",
    tag: "alerte-engrais", renotify: true, data: {url: d.url || "./#marche"},
  }));
});

// toucher la notification : l'appli s'ouvre (ou revient au premier plan) sur l'onglet Marché
self.addEventListener("notificationclick", ev => {
  ev.notification.close();
  const url = new URL(ev.notification.data && ev.notification.data.url || "./#marche", self.registration.scope).href;
  ev.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(fen => {
    const f = fen.find(c => c.url.startsWith(self.registration.scope));
    if (f) return f.navigate(url).then(c => (c || f).focus());
    return self.clients.openWindow(url);
  }));
});
