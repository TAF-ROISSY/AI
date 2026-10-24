/* English Co-Pilot service worker: the app opens even without network */
const CACHE = 'copilot-v2.1';
const CORE = ['./', './index.html', './manifest.json', './icon-180.png', './icon-192.png', './icon-512.png'];
const OPTIONAL = ['https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(CORE);
    await Promise.all(OPTIONAL.map(u => c.add(new Request(u, { mode:'cors' })).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('copilot-') && k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

const timeout = (ms) => new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms));

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;
  const url = new URL(req.url);
  if(url.hostname === 'api.anthropic.com') return;              // never cache the AI

  // the page itself: fresh copy when the network answers quickly, cached copy otherwise
  if(req.mode === 'navigate' || (url.origin === location.origin && /\/(index\.html)?$/.test(url.pathname))){
    e.respondWith((async () => {
      const c = await caches.open(CACHE);
      try{
        const r = await Promise.race([fetch(req), timeout(4000)]);
        if(r && r.ok){ c.put('./index.html', r.clone()); return r; }
        throw new Error('bad');
      }catch(_){
        return (await c.match('./index.html')) || (await c.match('./')) || Response.error();
      }
    })());
    return;
  }

  // icons, fonts and the PDF library: cache first, then network (and keep a copy)
  if(url.origin === location.origin || /(^|\.)(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com)$/.test(url.hostname)){
    e.respondWith((async () => {
      const c = await caches.open(CACHE);
      const hit = await c.match(req);
      if(hit) return hit;
      try{
        const r = await fetch(req);
        if(r && (r.ok || r.type === 'opaque')) c.put(req, r.clone());
        return r;
      }catch(_){ return Response.error(); }
    })());
  }
});
