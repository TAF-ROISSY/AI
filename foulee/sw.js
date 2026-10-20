// Foulée — service worker : appli disponible hors ligne, mises à jour récupérées en arrière-plan.
const CACHE = 'foulee-v9.4';
const TILES = 'foulee-tiles'; // cartes hors ligne enregistrées par l'appli (jamais vidé à la mise à jour)
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png', './icon-maskable.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== TILES).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  // Tuiles de carte : servies depuis les cartes hors ligne si elles y sont, sinon réseau (rien n'est ajouté automatiquement).
  if (req.method === 'GET' && /(^|\.)tile\.opentopomap\.org$|basemaps\.cartocdn\.com$/.test(url.hostname)) {
    e.respondWith(caches.open(TILES).then(c => c.match(req.url)).then(hit => hit || fetch(req)).catch(() => fetch(req)));
    return;
  }
  // Strava, API Claude et autres domaines : jamais interceptés ni mis en cache.
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  // Page : réseau d'abord (pour avoir la dernière version), cache si hors ligne.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req, { cache: 'no-cache' })
        .then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put('./index.html', copy)); return res; })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }
  // Fichiers statiques : cache d'abord, rafraîchi en arrière-plan.
  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req, { cache: 'no-cache' }).then(res => { if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); } return res; }).catch(() => hit);
      return hit || net;
    })
  );
});
