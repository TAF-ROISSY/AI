import W,{slotBest,slotMsgs,slotRun} from './worker.mjs';
const kv=new Map();const KV={get:async(k,t)=>{const v=kv.get(k);return v==null?null:t==='json'?JSON.parse(v):v;},put:async(k,v)=>kv.set(k,v),delete:async k=>kv.delete(k),list:async({prefix})=>({keys:[...kv.keys()].filter(k=>k.startsWith(prefix)).map(name=>({name}))})};
const env={FOULEE:KV,SITE:'https://example.github.io/ai/foulee/'};
const enc=new TextEncoder(),dec=new TextDecoder();const b64u=b=>Buffer.from(b).toString('base64url'),ub=s=>new Uint8Array(Buffer.from(s,'base64url'));
// client keys
const ck=await crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'},true,['deriveBits']);const cpub=new Uint8Array(await crypto.subtle.exportKey('raw',ck.publicKey));const auth=crypto.getRandomValues(new Uint8Array(16));
const sub={endpoint:'https://push.example.com/abc',keys:{p256dh:b64u(cpub),auth:b64u(auth)}};
const LIVE={st:'fini',pseudo:'Lucas',name:'Footing',t0:Date.now(),upd:Date.now(),el:0,dist:0,pos:[45.9,6.1],route:[[45.9,6.1],[45.95,6.1]],eta:Date.now()+3600e3,sos:false};
const pushed=[];
globalThis.fetch=async(url,opt={})=>{url=String(url);
  if(url.includes('open-meteo.com')){METEO.push(url);return new Response(JSON.stringify({hourly:HOURLY}),{status:200});}
  if(url.includes('cal.example.com/ok.ics'))return new Response('BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20261021T080000Z\nDTEND:20261021T170000Z\nSUMMARY:Boulot\nEND:VEVENT\nEND:VCALENDAR',{status:200});
  if(url.includes('cal.example.com/bad'))return new Response('<html>nope</html>',{status:200});
  if(url.includes('api.github.com/gists/'))return new Response(JSON.stringify({files:{'foulee-live.json':{content:JSON.stringify(LIVE)}}}),{status:200});
  if(url.startsWith('https://push.example.com')){pushed.push({h:opt.headers,b:new Uint8Array(opt.body)});return new Response('',{status:201});}
  throw new Error('unexpected '+url);};
async function hk(salt,ikm,info,len){const k=await crypto.subtle.importKey('raw',ikm,'HKDF',false,['deriveBits']);return new Uint8Array(await crypto.subtle.deriveBits({name:'HKDF',hash:'SHA-256',salt,info},k,len*8));}
const cat=(...a)=>{const o=new Uint8Array(a.reduce((x,y)=>x+y.length,0));let i=0;for(const x of a){o.set(x,i);i+=x.length;}return o;};
async function decrypt(b){const salt=b.slice(0,16),idlen=b[20],as=b.slice(21,21+idlen),ct=b.slice(21+idlen);const asK=await crypto.subtle.importKey('raw',as,{name:'ECDH',namedCurve:'P-256'},false,[]);
  const sh=new Uint8Array(await crypto.subtle.deriveBits({name:'ECDH',public:asK},ck.privateKey,256));const ikm=await hk(auth,sh,cat(enc.encode('WebPush: info\0'),cpub,as),32);
  const cek=await hk(salt,ikm,enc.encode('Content-Encoding: aes128gcm\0'),16),nonce=await hk(salt,ikm,enc.encode('Content-Encoding: nonce\0'),12);const key=await crypto.subtle.importKey('raw',cek,'AES-GCM',false,['decrypt']);
  const pt=new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM',iv:nonce},key,ct));return JSON.parse(dec.decode(pt.slice(0,pt.lastIndexOf(2))));}

// météo synthétique : 5 jours, chaud l'après-midi, pluie le samedi
const METEO=[];
function mk(){const time=[],at=[],pp=[],w=[];const d0=new Date();for(let d=0;d<5;d++){const dt=new Date(d0.getTime()+d*864e5),ds=dt.toISOString().slice(0,10);for(let h=0;h<24;h++){time.push(ds+'T'+String(h).padStart(2,'0')+':00');at.push(Math.round(10+14*Math.max(0,Math.sin((h-8)/12*Math.PI))));pp.push(d===3?80:5);w.push(h>15?25:8);}}return {time,apparent_temperature:at,precipitation_probability:pp,wind_speed_10m:w};}
const HOURLY=mk();
const call=async(p,b,m)=>{const r=await W.fetch(new Request('https://w.x'+p,b?{method:'POST',body:JSON.stringify(b)}:{}),env);return {s:r.status,j:r.headers.get('content-type').includes('json')?await r.json():await r.text()};};
const day=n=>new Date(Date.now()+n*864e5).toISOString().slice(0,10);
console.log('best', JSON.stringify(slotBest(HOURLY,day(1),120)));
console.log('slot sans abonnement', (await call('/slot',{endpoint:sub.endpoint,ll:[49.3,2.4],sess:[]})).s);
await call('/sub',{sub,people:[],tz:'Europe/Paris'});
const r1=await call('/slot',{endpoint:sub.endpoint,ll:[49.312,2.456],tz:'Europe/Paris',sess:[{d:day(1),t:'Sortie longue',min:110},{d:day(1),t:'Gainage',min:20}]});console.log('slot', r1.s, JSON.stringify(r1.j));
console.log('stored', [...kv.keys()].filter(k=>k.startsWith('sl:')||k==='slots').length, JSON.parse(kv.get([...kv.keys()].find(k=>k.startsWith('sl:')))).ll);
// trouver un fuseau où il est 19 h maintenant
let tz=null;for(let o=-12;o<=14;o++){const z='Etc/GMT'+(o<=0?'+'+(-o):'-'+o);const h=+new Intl.DateTimeFormat('en-GB',{timeZone:z,hour:'2-digit',hour12:false}).format(new Date())%24;if(h===19){tz=z;break;}}
const id=[...kv.keys()].find(k=>k.startsWith('sl:'));const v=JSON.parse(kv.get(id));
const loc=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());const tom=new Date(loc+'T12:00:00Z');tom.setUTCDate(tom.getUTCDate()+1);
v.tz=tz;v.sess=[{d:tom.toISOString().slice(0,10),t:'Sortie longue',min:110}];kv.set(id,JSON.stringify(v));
const n1=await slotRun(env);console.log('tz',tz,'envoyées',n1,'push',pushed.length);
if(pushed.length){const m=await decrypt(pushed[pushed.length-1].b);console.log('message', JSON.stringify(m));}
console.log('pas deux fois', await slotRun(env));
console.log('jeudi', JSON.stringify(slotMsgs({sess:[{d:'2026-10-24',t:'Sortie longue',min:150},{d:'2026-10-25',t:'Footing',min:45}]},{time:HOURLY.time.map((t,i)=>['2026-10-23','2026-10-24','2026-10-25','2026-10-26','2026-10-27'][Math.floor(i/24)]+t.slice(10)),apparent_temperature:HOURLY.apparent_temperature,precipitation_probability:HOURLY.time.map((t,i)=>Math.floor(i/24)===2?85:5),wind_speed_10m:HOURLY.wind_speed_10m},{date:'2026-10-22',h:19,wd:4})));
console.log('ics ok', JSON.stringify(await call('/ics?u='+encodeURIComponent('webcal://cal.example.com/ok.ics'))).slice(0,80));
console.log('ics bad', JSON.stringify(await call('/ics?u='+encodeURIComponent('https://cal.example.com/bad'))));
console.log('ics invalide', JSON.stringify(await call('/ics?u=javascript:alert(1)')));
