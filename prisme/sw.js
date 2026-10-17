// Prisme 1.0.0 : fonctionne sans réseau une fois ouvert une première fois
const C='prisme-1.0.0';
const SHELL=['./','index.html','manifest.webmanifest','icon-180.png','icon-192.png','icon-512.png'].concat(["https://cdn.jsdelivr.net/npm/mp4box@0.5.2/dist/mp4box.all.min.js", "https://cdn.jsdelivr.net/npm/mp4-muxer@5.1.3/build/mp4-muxer.js", "https://cdn.jsdelivr.net/npm/exifr@7.1.3/dist/full.umd.js", "https://cdn.jsdelivr.net/npm/piexifjs@1.0.6/piexif.js", "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"]);
self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>Promise.all(SHELL.map(u=>c.add(new Request(u,{mode:u.startsWith('http')?'cors':'same-origin'})).catch(()=>{})))).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const r=e.request; if(r.method!=='GET'||r.url.startsWith('blob:'))return;
  const page=r.mode==='navigate';
  e.respondWith(page
    ? fetch(r).then(res=>{const cp=res.clone();caches.open(C).then(c=>c.put('index.html',cp));return res;}).catch(()=>caches.match('index.html'))
    : caches.match(r).then(m=>m||fetch(r).then(res=>{if(res.ok){const cp=res.clone();caches.open(C).then(c=>c.put(r,cp));}return res;})));
});
