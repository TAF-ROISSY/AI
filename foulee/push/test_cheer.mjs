import W from './worker.mjs';const kv=new Map();const env={FOULEE:{get:async(k,t)=>{const v=kv.get(k);return v==null?null:t==='json'?JSON.parse(v):v},put:async(k,v)=>kv.set(k,v),delete:async k=>kv.delete(k)}};
const G='a'.repeat(32);const call=async(p,b)=>(await W.fetch(new Request('https://w.x'+p,b?{method:'POST',body:JSON.stringify(b)}:{}),env)).json();
console.log(await call('/cheer',{g:G,from:'Maman',text:'Allez Lucas ! 👏'}));const t0=Date.now();await new Promise(r=>setTimeout(r,5));console.log(await call('/cheer',{g:G,from:'Papa',text:'Courage'}));
console.log(JSON.stringify(await call('/cheer?g='+G)));console.log(JSON.stringify(await call('/cheer?g='+G+'&since='+t0)));console.log(await call('/cheer',{g:'zz',text:'x'}));
