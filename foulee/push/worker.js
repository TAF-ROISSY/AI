// Foulée — serveur de notifications (Cloudflare Worker, gratuit).
// Surveille les gists « suivi en direct » des proches et envoie des notifications Web Push :
// départ, arrivée, alerte d’immobilité, arrivée à la maison, éloignement, sortie du parcours.
// Bindings : KV « FOULEE » ; secret GITHUB_TOKEN (jeton sans aucun droit, indispensable : sans lui GitHub limite à 60 lectures / h) ; variable SITE (adresse de Foulée).
// Déclencheur Cron : « * * * * * » (toutes les minutes).

const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' };
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'Content-Type': 'application/json', ...CORS } });
const enc = new TextEncoder();
const b64u = b => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const ub64 = s => { s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; return Uint8Array.from(atob(s), c => c.charCodeAt(0)); };
const cat = (...a) => { const n = a.reduce((x, y) => x + y.length, 0), o = new Uint8Array(n); let i = 0; for (const x of a) { o.set(x, i); i += x.length; } return o; };
const sha = async t => b64u(await crypto.subtle.digest('SHA-256', enc.encode(t))).slice(0, 22);
const km = (a, b) => { const R = 6371, t = x => x * Math.PI / 180, dLa = t(b[0] - a[0]), dLo = t(b[1] - a[1]), h = Math.sin(dLa / 2) ** 2 + Math.cos(t(a[0])) * Math.cos(t(b[0])) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };

// ---------- VAPID ----------
async function vapid(env) {
  let v = await env.FOULEE.get('vapid', 'json');
  if (!v) {
    const k = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
    const pub = await crypto.subtle.exportKey('raw', k.publicKey), jwk = await crypto.subtle.exportKey('jwk', k.privateKey);
    v = { pub: b64u(pub), jwk }; await env.FOULEE.put('vapid', JSON.stringify(v));
  }
  return v;
}
async function vapidAuth(env, endpoint) {
  const v = await vapid(env), aud = new URL(endpoint).origin;
  const h = b64u(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' }))), p = b64u(enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: env.SUBJECT || 'mailto:foulee@example.com' })));
  const key = await crypto.subtle.importKey('jwk', v.jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, enc.encode(h + '.' + p));
  return `vapid t=${h}.${p}.${b64u(sig)}, k=${v.pub}`;
}
// ---------- Chiffrement aes128gcm (RFC 8291) ----------
async function hkdf(salt, ikm, info, len) {
  const k = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, k, len * 8));
}
export async function encrypt(sub, text) {
  const ua = ub64(sub.keys.p256dh), auth = ub64(sub.keys.auth), salt = crypto.getRandomValues(new Uint8Array(16));
  const eph = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const as = new Uint8Array(await crypto.subtle.exportKey('raw', eph.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', ua, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, eph.privateKey, 256));
  const ikm = await hkdf(auth, shared, cat(enc.encode('WebPush: info\0'), ua, as), 32);
  const cek = await hkdf(salt, ikm, enc.encode('Content-Encoding: aes128gcm\0'), 16), nonce = await hkdf(salt, ikm, enc.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, cat(enc.encode(text), new Uint8Array([2]))));
  const head = new Uint8Array(21); head.set(salt, 0); new DataView(head.buffer).setUint32(16, 4096); head[20] = 65;
  return cat(head, as, ct);
}
export async function sendPush(env, sub, msg) {
  const body = await encrypt(sub, JSON.stringify(msg));
  const r = await fetch(sub.endpoint, { method: 'POST', body, headers: { TTL: '3600', Urgency: msg.urgent ? 'high' : 'normal', 'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', Authorization: await vapidAuth(env, sub.endpoint) } });
  return r.status;
}
async function idx(env, id, add) { const L = (await env.FOULEE.get('subs', 'json')) || [], has = L.includes(id); if (add && !has) L.push(id); else if (!add && has) L.splice(L.indexOf(id), 1); else return; await env.FOULEE.put('subs', JSON.stringify(L)); }
// ---------- Logique des événements ----------
function liveSt(d) { if (!d) return 'none'; if (d.sos && d.st !== 'fini') return 'alert'; if (d.st === 'fini' || Date.now() - d.upd > 15 * 60e3) return 'fini'; return d.st; }
function offRoute(d) { if (!d.route || d.route.length < 2 || !d.pos) return null; let m = 1e9; for (const p of d.route) m = Math.min(m, km(p, d.pos)); return m; }
export function events(name, prev, d, z) {
  const out = [], s = liveSt(d), was = prev.s || 'none', live = x => ['run', 'pause', 'alert'].includes(x), now = {};
  now.s = s;
  if (s === 'alert' && was !== 'alert') out.push({ title: `⚠ Alerte : ${name}`, body: `${name} ne bouge plus depuis plusieurs minutes et n’a pas répondu. Appelle-le ou ouvre sa position.`, urgent: 1 });
  else if (live(s) && !live(was)) out.push({ title: `${name} part courir`, body: `${d.name || 'Sortie'}${d.eta ? ' · arrivée estimée ' + new Date(d.eta).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: z.tz || 'Europe/Paris' }) : ''}` });
  else if (s === 'fini' && live(was)) out.push({ title: `${name} a terminé`, body: `${(d.dist / 1000).toFixed(1).replace('.', ',')} km en ${Math.round(d.el / 60)} min.` });
  if (live(s) && d.pos) {
    if (z.home) { const dk = km(z.home, d.pos), inside = dk * 1000 <= (z.r || 200); now.in = inside; if (inside && prev.in === false) out.push({ title: `${name} est arrivé à la maison`, body: `${(d.dist / 1000).toFixed(1).replace('.', ',')} km parcourus.` });
      if (z.far > 0) { const far = dk > z.far; now.far = far; if (far && !prev.far && live(was)) out.push({ title: `${name} s’éloigne`, body: `${name} est à ${dk.toFixed(1).replace('.', ',')} km de la maison (seuil ${z.far} km).`, urgent: 1 }); } }
    const off = offRoute(d); if (off != null) { const o = off > 0.4; now.off = o; if (o && !prev.off) out.push({ title: `${name} a quitté son parcours`, body: `À ${Math.round(off * 1000)} m du tracé prévu.` }); }
  }
  if (!live(s)) { now.in = null; now.far = false; now.off = false; }
  return { out, now };
}
async function getLive(env, g) {
  const h = { Accept: 'application/vnd.github+json', 'User-Agent': 'foulee-push' }; if (env.GITHUB_TOKEN) h.Authorization = 'Bearer ' + env.GITHUB_TOKEN;
  const r = await fetch('https://api.github.com/gists/' + g, { headers: h }); if (!r.ok) return null;
  const j = await r.json(), f = j.files && j.files['foulee-live.json']; if (!f) return null;
  return JSON.parse(f.truncated ? await (await fetch(f.raw_url)).text() : f.content);
}
export async function run(env) {
  const ids = (await env.FOULEE.get('subs', 'json')) || [], subs = [];
  for (const id of ids) { const v = await env.FOULEE.get(id, 'json'); if (v) subs.push({ id, ...v }); }
  if (subs.length !== ids.length) await env.FOULEE.put('subs', JSON.stringify(subs.map(s => s.id)));
  const gists = [...new Set(subs.flatMap(s => (s.people || []).map(p => p.g)))], data = {};
  await Promise.all(gists.map(async g => { try { data[g] = await getLive(env, g); } catch (e) { } }));
  let sent = 0;
  for (const s of subs) for (const p of s.people || []) {
    const d = data[p.g]; if (!d) continue; const key = 'st:' + s.id.slice(4) + ':' + p.g, prev = (await env.FOULEE.get(key, 'json')) || {};
    const { out, now } = events(p.n || d.pseudo || 'Ton proche', prev, d, { home: p.home, r: p.r, far: p.far, tz: s.tz });
    if (JSON.stringify(now) !== JSON.stringify(prev)) await env.FOULEE.put(key, JSON.stringify(now), { expirationTtl: 30 * 86400 });
    for (const m of out) { const st = await sendPush(env, s.sub, { ...m, url: (env.SITE || '') + 'suivi.html', tag: p.g }); sent++; if (st === 404 || st === 410) { await env.FOULEE.delete(s.id); await idx(env, s.id, false); break; } }
  }
  return { subs: subs.length, gists: gists.length, sent };
}
export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
    const u = new URL(req.url);
    try {
      if (u.pathname === '/vapid') return json({ key: (await vapid(env)).pub });
      if (u.pathname === '/sub' && req.method === 'POST') { const b = await req.json(); if (!b.sub || !b.sub.endpoint || !b.sub.keys) return json({ error: 'abonnement invalide' }, 400);
        const people = (b.people || []).filter(p => /^[0-9a-f]{20,40}$/i.test(p.g)).slice(0, 10).map(p => ({ g: p.g.toLowerCase(), n: String(p.n || '').slice(0, 30), home: Array.isArray(p.home) ? p.home.map(Number) : null, r: +p.r || 200, far: +p.far || 0 }));
        const id = 'sub:' + await sha(b.sub.endpoint); await env.FOULEE.put(id, JSON.stringify({ sub: b.sub, people, tz: b.tz || 'Europe/Paris', at: Date.now() }), { expirationTtl: 180 * 86400 }); await idx(env, id, true); return json({ ok: true, people: people.length }); }
      if (u.pathname === '/unsub' && req.method === 'POST') { const b = await req.json(), id = 'sub:' + await sha(b.endpoint || ''); await env.FOULEE.delete(id); await idx(env, id, false); return json({ ok: true }); }
      if (u.pathname === '/test' && req.method === 'POST') { const b = await req.json(); const v = await env.FOULEE.get('sub:' + await sha(b.endpoint || ''), 'json'); if (!v) return json({ error: 'abonnement inconnu' }, 404);
        const st = await sendPush(env, v.sub, { title: 'Test Foulée Suivi', body: 'Les notifications marchent. Tu seras prévenue au départ, à l’arrivée et en cas d’alerte.', url: (env.SITE || '') + 'suivi.html' }); return json({ ok: st < 300, status: st }); }
      if (u.pathname === '/cheer' && req.method === 'POST') { const b = await req.json(); if (!/^[0-9a-f]{20,40}$/i.test(b.g || '') || !String(b.text || '').trim()) return json({ error: 'message invalide' }, 400);
        const k = 'ch:' + b.g.toLowerCase(), L = (await env.FOULEE.get(k, 'json')) || [], m = { id: Date.now(), from: String(b.from || 'Un proche').slice(0, 30), text: String(b.text).trim().slice(0, 140) };
        L.push(m); await env.FOULEE.put(k, JSON.stringify(L.slice(-20)), { expirationTtl: 86400 }); return json({ ok: true, id: m.id }); }
      if (u.pathname === '/cheer' && req.method === 'GET') { const g = (u.searchParams.get('g') || '').toLowerCase(), since = +u.searchParams.get('since') || 0; if (!/^[0-9a-f]{20,40}$/.test(g)) return json({ list: [] });
        const L = (await env.FOULEE.get('ch:' + g, 'json')) || []; return json({ list: L.filter(m => m.id > since) }); }
      if (u.pathname === '/run') return json(await run(env));
      return json({ app: 'Foulée push', ok: true });
    } catch (e) { return json({ error: String(e.message || e) }, 500); }
  },
  async scheduled(ev, env, ctx) { ctx.waitUntil(run(env)); }
};
