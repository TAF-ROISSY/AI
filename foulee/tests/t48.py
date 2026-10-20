"""v9.6 : plan glissant (séance manquée déplacée / abandonnée), journal vocal (analyse locale et coach), widget séance du jour (gist + script Scriptable), duel du mois, course contre son record sur un parcours connu (fantôme)."""
import os, json, subprocess
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;const _dn=Date.now.bind(Date);window._dn=_dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
GH={}
async def gh(route):
    r=route.request;u=r.url
    if r.method=='POST' and u.endswith('/gists'):
        GH['w1']=json.loads(r.post_data)['files']; await route.fulfill(status=201,content_type='application/json',body=json.dumps({'id':'w1'})); return
    if r.method=='PATCH': GH['patch']=GH.get('patch',0)+1; GH['w1']=json.loads(r.post_data)['files']; await route.fulfill(status=200,content_type='application/json',body='{"id":"w1"}'); return
    await route.fulfill(status=404,content_type='application/json',body='{}')
async def claude(route):
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":"journal_sortie","input":{"ressenti":3,"douleurs":[{"zone":"genou","niveau":2}],"resume":"Séance exigeante, genou gênant en descente."}}],"stop_reason":"tool_use"}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation','clipboard-read','clipboard-write'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.github.com/**',gh); await A.route('https://api.anthropic.com/**',claude)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();S.settings.start=iso(mondayOf(new Date(Date.now()-8*864e5)));S.done={};save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    # --- plan glissant
    print('missed', await A.evaluate("JSON.stringify(missedList().map(m=>[iso(m.dt),m.o.k,mvKind(m.o.k)]))"))
    print('card', await A.evaluate("$('[data-page=today]').innerText.includes('Séance manquée')"))
    await A.locator('[data-page=today] .mv-c').screenshot(path='v96_missed.png')
    r=await A.evaluate("""(()=>{const L=missedList();const m=L.find(x=>mvKind(x.o.k)==='hard')||L[0];const sg=mvSuggest(m);const to=sg?iso(sg):iso(new Date());mvSet(m.o.k,m.w,m.d,to);const T=parseISO(to),w=weekIdx(T),d=dayIdx(T);
      return JSON.stringify({k:m.o.k,kind:mvKind(m.o.k),to,onTarget:daySessions(w,d).some(o=>o.k===m.o.k&&o.moved),onOrigin:daySessions(m.w,m.d).some(o=>o.k===m.o.k),txt:strip(daySessions(w,d).find(o=>o.k===m.o.k).s).slice(-30)});})()""")
    print('moved', r)
    r=await A.evaluate("(()=>{const L=missedList();if(!L.length)return 'none';const m=L[0];mvDrop(m.o.k,m.w,m.d);return JSON.stringify({k:m.o.k,gone:!daySessions(m.w,m.d).some(o=>o.k===m.o.k),left:missedList().length})})()"); print('drop', r)
    print('synced mv', await A.evaluate("'mv' in syncPayload().data"))
    # --- journal vocal
    k=await A.evaluate("(()=>{const w=weekIdx();for(let d=0;d<7;d++){const o=daySessions(w,d,'run')[0];if(o)return o.k;}})()")
    for t in ['Super séance, bonnes sensations, nickel','Très dur, explosé à la fin, petite gêne au mollet gauche','Sortie difficile et douleur forte au genou dans la descente','Trop facile, j’aurais pu en faire plus']:
        print('local', json.dumps(await A.evaluate("t=>vjLocal(t)",t),ensure_ascii=False))
    await A.evaluate(f"openFb('{k}')"); print('vj block', await A.evaluate("!!$('#sheetBody #vjMic')"))
    await A.locator('#vjMic').click(); await A.fill('#vjT','Séance dure, jambes lourdes, un peu mal au tibia'); await A.locator('#vjGo').click(); await A.wait_for_timeout(200)
    print('vj out', await A.evaluate("$('#vjOut').innerText.replace(/\\n/g,' | ')"))
    await A.screenshot(path='v96_vj.png',full_page=True)
    await A.locator('#vjOut button:has-text("Valider")').click(); await A.wait_for_timeout(200)
    print('applied', await A.evaluate(f"JSON.stringify(S.fb['{k}'])"), await A.evaluate("JSON.stringify(S.check[iso(new Date())].pain)"))
    await A.evaluate("setKey('sk-ant-test')"); await A.evaluate(f"openFb('{k}')"); await A.locator('#vjMic').click(); await A.fill('#vjT','Dur, genou gênant en descente'); await A.locator('#vjGo').click(); await A.wait_for_timeout(500)
    print('coach', await A.evaluate("$('#vjOut').innerText.replace(/\\n/g,' | ')")); await A.evaluate("closeSettings()")
    # --- widget
    await A.evaluate("setVC({token:'ghp_test'})"); await A.evaluate("widToggle(true)"); await A.wait_for_timeout(600)
    print('widget', await A.evaluate("S.widGist"), await A.evaluate("window.__widPushed"), 'file', 'foulee-widget.json' in GH.get('w1',{}), 'script', await A.evaluate("$('#wd_s')&&$('#wd_s').value.includes('w1')"))
    P=json.loads(GH['w1']['foulee-widget.json']['content']); print('payload', len(P['days']), P['days'][0]['l'], P['forme'], [x['t'] for x in P['days'][0]['s']][:2])
    open('/tmp/claude-0/v95/wid.js','w').write('async function main(){'+await A.evaluate("widScript()")+'}')
    print('script syntax', subprocess.run(['node','--check','/tmp/claude-0/v95/wid.js'],capture_output=True,text=True).returncode==0)
    await A.screenshot(path='v96_widget.png',full_page=True); await A.evaluate("closeSettings()")
    await A.evaluate("widPush(false)"); await A.wait_for_timeout(300); print('no change no push', GH.get('patch',0))
    # --- duel
    await A.evaluate("(()=>{const now=new Date(),ym=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0');S.friends=[{id:'f1'}];FR.data.f1={ok:true,pseudo:'Lucas',mois:{[ym]:{km:30,dp:900,h:4,n:6}}};S.duel='f1';save();DUELF=Date.now();renderToday();})()")
    print('duel', await A.evaluate("$('[data-page=today] .duel')?$('[data-page=today] .duel').innerText.replace(/\\n/g,' '):'none'"))
    await A.locator('[data-page=today] .duel').screenshot(path='v96_duel.png')
    await A.evaluate("duelShare()"); await A.wait_for_timeout(800); print('duel img', await A.evaluate("window.__duelImg"))
    # --- fantôme
    gid=await A.evaluate("(routeSrcs().find(x=>x.id.startsWith('gh:'))||{}).id||null"); print('ghost src', gid, await A.evaluate("(routeSrcs().find(x=>x.id.startsWith('gh:'))||{}).n||''"))
    if gid:
        await A.evaluate(f"routeOpen('{gid}')"); print('ghost', await A.evaluate("JSON.stringify({plan:GR.route.plan.length,lbl:GR.route.planLbl,step:GR.steps[0].n,lo:Math.round(GR.steps[0].lo)})"))
        st=await A.evaluate("GR.route.pts[0].slice(0,2)"); await ctx.set_geolocation({'latitude':st[0],'longitude':st[1]})
        await A.evaluate("window.__now=_dn();grStart();window.__said=[]")
        await A.evaluate("""(()=>{const P=GR.route.pts;let t=window.__now;const tot=GR.route.ghost.t[GR.route.ghost.t.length-1]*1.08,L=GR.route.len;let c=0;for(let i=1;i<P.length;i++){const dd=P[i][3]-P[i-1][3],n=Math.max(1,Math.ceil(dd/10));for(let j=1;j<=n;j++){const f=j/n;t+=dd/n/L*tot*1000;window.__now=t;grFeed({t,lat:P[i-1][0]+(P[i][0]-P[i-1][0])*f,lon:P[i-1][1]+(P[i][1]-P[i-1][1])*f,acc:5});if(++c%3===0)grTick();}}})()""")
        s=await A.evaluate("window.__said"); hit=[x for x in s if 'record' in x]; print('said ghost', len(hit), hit[:2]);print('dbg', await A.evaluate("JSON.stringify({s:GR.route.s,len:GR.route.len,el:grElapsed()/1000,gt:GR.route.ghost.t.slice(-1)[0],gd:GR.route.ghost.d.slice(-1)[0],dist:GR.dist,said:window.__said.slice(0,4),on:GR.on,pts:GR.route.pts.length})"))
        await A.evaluate("grDraw()"); print('ghost line', await A.evaluate("$('#grBody').innerText.match(/👻[^\\n·]*/)?.[0]||$('#grBody .rt-box')?.innerText.slice(0,120)"))
        await A.evaluate("grStop(false);$('#grv').classList.remove('on');window.__now=null")
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
