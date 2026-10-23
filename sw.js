/* Dropline offline support: keeps a copy of the app on the phone so it opens with no signal.
   With signal, the latest version is loaded from the website as usual (and the copy is refreshed). */
const SHELL = "dropline-shell-v1";
const TILES = "dropline-tiles-v1";
const LIBS = [
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.2/Sortable.min.js"
];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => Promise.all([
    c.add(new Request("./", {cache: "reload"})).catch(() => {}),
    ...LIBS.map(u => c.add(new Request(u, {mode: "cors"})).catch(() => {}))
  ])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("dropline-shell-") && k !== SHELL).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
function timeout(ms){ return new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms)); }
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  // the app page: newest from the website when there is signal (4 s limit), otherwise the saved copy
  if (req.mode === "navigate" || (url.origin === location.origin && (url.pathname.endsWith("/") || url.pathname.endsWith("/index.html")))){
    e.respondWith((async () => {
      const c = await caches.open(SHELL);
      try{
        const r = await Promise.race([fetch(req, {cache: "no-cache"}), timeout(4000)]);
        if (r && r.ok){ c.put("./", r.clone()).catch(() => {}); return r; }
        throw new Error("bad");
      }catch(err){
        const hit = await c.match("./") || await c.match(req);
        if (hit) return hit;
        return Response.redirect(new URL("offline.html", self.registration.scope).href, 302);
      }
    })());
    return;
  }
  // map libraries and fonts: saved copy first
  if (/cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com/.test(url.host)){
    e.respondWith(caches.open(SHELL).then(async c => {
      const hit = await c.match(req); if (hit) return hit;
      const r = await fetch(req); if (r && (r.ok || r.type === "opaque")) c.put(req, r.clone()).catch(() => {}); return r;
    }));
    return;
  }
  // map pictures: saved copy first (filled by "Prepare for offline"), else the network
  if (/tile\.openstreetmap\.org/.test(url.host)){
    e.respondWith(caches.open(TILES).then(async c => (await c.match(req.url)) || fetch(req)));
    return;
  }
});
