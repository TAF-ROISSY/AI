import W,{events} from './worker.mjs';
const kv=new Map();const KV={get:async(k,t)=>{const v=kv.get(k);return v==null?null:t==='json'?JSON.parse(v):v;},put:async(k,v)=>kv.set(k,v),delete:async k=>kv.delete(k),list:async({prefix})=>({keys:[...kv.keys()].filter(k=>k.startsWith(prefix)).map(name=>({name}))})};
const env={FOULEE:KV,SITE:'https://example.github.io/ai/foulee/'};
const enc=new TextEncoder(),dec=new TextDecoder();const b64u=b=>Buffer.from(b).toString('base64url'),ub=s=>new Uint8Array(Buffer.from(s,'base64url'));
// client keys
const ck=await crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'},true,['deriveBits']);const cpub=new Uint8Array(await crypto.subtle.exportKey('raw',ck.publicKey));const auth=crypto.getRandomValues(new Uint8Array(16));
const sub={endpoint:'https://push.example.com/abc',keys:{p256dh:b64u(cpub),auth:b64u(auth)}};
const LIVE={st:'fini',pseudo:'Lucas',name:'Footing',t0:Date.now(),upd:Date.now(),el:0,dist:0,pos:[45.9,6.1],route:[[45.9,6.1],[45.95,6.1]],eta:Date.now()+3600e3,sos:false};
const pushed=[];
globalThis.fetch=async(url,opt={})=>{url=String(url);
  if(url.includes('api.github.com/gists/'))return new Response(JSON.stringify({files:{'foulee-live.json':{content:JSON.stringify(LIVE)}}}),{status:200});
  if(url.startsWith('https://push.example.com')){pushed.push({h:opt.headers,b:new Uint8Array(opt.body)});return new Response('',{status:201});}
  throw new Error('unexpected '+url);};
async function hk(salt,ikm,info,len){const k=await crypto.subtle.importKey('raw',ikm,'HKDF',false,['deriveBits']);return new Uint8Array(await crypto.subtle.deriveBits({name:'HKDF',hash:'SHA-256',salt,info},k,len*8));}
const cat=(...a)=>{const o=new Uint8Array(a.reduce((x,y)=>x+y.length,0));let i=0;for(const x of a){o.set(x,i);i+=x.length;}return o;};
async function decrypt(b){const salt=b.slice(0,16),idlen=b[20],as=b.slice(21,21+idlen),ct=b.slice(21+idlen);const asK=await crypto.subtle.importKey('raw',as,{name:'ECDH',namedCurve:'P-256'},false,[]);
  const sh=new Uint8Array(await crypto.subtle.deriveBits({name:'ECDH',public:asK},ck.privateKey,256));const ikm=await hk(auth,sh,cat(enc.encode('WebPush: info\0'),cpub,as),32);
  const cek=await hk(salt,ikm,enc.encode('Content-Encoding: aes128gcm\0'),16),nonce=await hk(salt,ikm,enc.encode('Content-Encoding: nonce\0'),12);const key=await crypto.subtle.importKey('raw',cek,'AES-GCM',false,['decrypt']);
  const pt=new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:nonce},key,ct));return JSON.parse(dec.decode(pt.slice(0,pt.lastIndexOf(2))));}
async function verify(h){const m=h.Authorization.match(/t=([^,]+), k=(.+)/);const [a,b,c]=m[1].split('.');const pk=await crypto.subtle.importKey('raw',ub(m[2]),{name:'ECDSA',namedCurve:'P-256'},false,['verify']);
  const ok=await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},pk,ub(c),enc.encode(a+'.'+b));return ok&&JSON.parse(Buffer.from(b,'base64url')).aud==='https://push.example.com';}
const call=(p,body)=>W.fetch(new Request('https://w.example'+p,body?{method:'POST',body:JSON.stringify(body)}:{}),env);
const v=await (await call('/vapid')).json();console.log('vapid key len',ub(v.key).length);
const G='a'.repeat(32);console.log('sub',await (await call('/sub',{sub,people:[{g:G,n:'Lucas',home:[45.95,6.1],r:300,far:4}],tz:'Asia/Bangkok'})).json());
const t=await (await call('/test',{endpoint:sub.endpoint})).json();console.log('test',t,'jwt ok',await verify(pushed.at(-1).h),'msg',(await decrypt(pushed.at(-1).b)).title);
const step=async(lbl,mut)=>{Object.assign(LIVE,mut,{upd:Date.now()});const n0=pushed.length;const r=await (await call('/run')).json();const msgs=[];for(const p of pushed.slice(n0))msgs.push((await decrypt(p.b)).title);console.log(lbl,JSON.stringify(r),msgs);};
await step('idle',{});
await step('start',{st:'run',dist:200,pos:[45.9,6.1]});
await step('same',{dist:800});
await step('off route',{pos:[45.92,6.12]});
await step('far',{pos:[45.99,6.1]});
await step('home',{pos:[45.95,6.1],dist:6000});
await step('alert',{st:'alert',sos:true});
await step('back ok',{st:'run',sos:false});
await step('finish',{st:'fini',el:3600,dist:9300});
globalThis.fetch=async(url,opt)=>String(url).includes('github')?new Response(JSON.stringify({files:{'foulee-live.json':{content:JSON.stringify({...LIVE,st:'run',upd:Date.now()})}}})):new Response('',{status:410});
console.log('expired',JSON.stringify(await (await call('/run')).json()),'subs left',[...kv.keys()].filter(k=>k.startsWith('sub:')).length);
