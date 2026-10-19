"""v8.4 : test VMA guidé (demi-Cooper au GPS, voix, recalcul des allures) et saisi ; coach pro (périodisation, réajustement IA des 7 jours appliqué au plan, annulation, retour au plan d'origine, auto du dimanche, calage sur la course) ; séance prévue écrite dans la description Strava."""
import os, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;window._dn=Date.now.bind(Date);const _dn=window._dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
calls=[];strava=[]
async def ant(r):
    b=json.loads(r.request.post_data); calls.append(b)
    msg=b['messages'][0]['content']; L=json.loads(msg.split('Séances à venir (JSON) : ')[1].split('\n')[0])
    run=[x for x in L if x['type']=='course']; mus=[x for x in L if x['type']=='muscu']
    adj=[]
    if run: adj.append({'cle':run[0]['cle'],'action':'alleger','titre':'Footing raccourci','detail':'6 km au lieu de 8, allure facile'})
    if len(run)>1: adj.append({'cle':run[1]['cle'],'action':'remplacer','titre':'Côtes 6 × 45 s','detail':'15 min échauffement, 6 côtes de 45 s, retour en trottinant'})
    if mus: adj.append({'cle':mus[0]['cle'],'action':'annuler','detail':'sommeil court deux nuits de suite'})
    adj.append({'cle':'inconnue','action':'annuler'})
    await r.fulfill(status=200,content_type='application/json',body=json.dumps({'content':[{'type':'tool_use','id':'t1','name':'reajuster_semaine','input':{'resume':'Charge en hausse et sommeil court : on allège.','ajustements':adj,'conseils':['Couche-toi 30 min plus tôt']}}],'stop_reason':'tool_use'}))
async def stv(r):
    req=r.request; strava.append((req.method,req.url,req.post_data))
    if req.method=='GET': await r.fulfill(status=200,content_type='application/json',body=json.dumps({'id':999,'name':'Course à pied le matin','description':'Belle sortie'}))
    else: await r.fulfill(status=200,content_type='application/json',body='{}')
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':49.2,'longitude':2.5},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.anthropic.com/**',ant); await A.route('https://www.strava.com/api/v3/activities/**',stv)
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll();showTab('plan')"); await A.wait_for_timeout(200)
    p0=await A.evaluate("JSON.stringify([fmtDur(getA().P.t10),fmtPace(getA().P.easyLo),fmtPace(getA().P.vma)])"); print('before', p0)
    print('cards', await A.evaluate("[...document.querySelectorAll('[data-page=plan] .card h2')].map(h=>h.textContent).filter(t=>/Coach pro|Test VMA/.test(t)).join(' | ')"), 'perio cells', await A.evaluate("document.querySelectorAll('[data-page=plan] .perio i').length"))
    # test VMA guidé : 15 min échauffement puis 6 min à 4,2 m/s (≈ 1512 m → 15,1 km/h)
    await A.evaluate("vmaOpen('demi')"); print('steps', await A.evaluate("JSON.stringify(GR.steps.map(s=>[s.k,s.t,!!s.test]))"))
    await A.evaluate("window.__now=_dn();window.__said=[];grStart();grNext();window.__said=[]")
    await A.evaluate("""(()=>{let lat=49.2,t=window.__now;for(let i=0;i<200;i++){t+=2000;window.__now=t;lat+=4.2*2/111320;grFeed({t,lat,lon:2.5,acc:5});grTick();if(GR.si!==1)break;}})()""")
    print('said', [x for x in await A.evaluate("window.__said") if 'Encore' in x or 'minute' in x or 'VMA' in x][:6])
    print('vma', await A.evaluate("JSON.stringify(vmaCur()&&{v:vmaCur().v,dist:vmaCur().dist,src:vmaCur().src})"), 'after', await A.evaluate("JSON.stringify([fmtDur(getA().P.t10),fmtPace(getA().P.easyLo),fmtPace(getA().P.vma),getA().P.src.name])"))
    await A.evaluate("grStop(false);GR.si=GR.steps.length;grDraw()"); print('done screen', await A.evaluate("$('#grBody').innerText.split('\\n')[1]")); await A.locator('#grv').screenshot(path='v_done.png'); await A.evaluate("$('#grv').classList.remove('on')")
    await A.evaluate("openVmaManual('piste')"); await A.fill('#vm_v','16.4'); await A.locator('#sheetBody button:has-text("Enregistrer")').click(); await A.wait_for_timeout(100)
    print('manual', await A.evaluate("vmaCur().v"), 'zones', await A.evaluate("vmaZones(16.4)[0].join(' ')"), 'synced', await A.evaluate("'vma' in syncPayload().data"))
    await A.evaluate("renderAll();showTab('plan')"); await A.wait_for_timeout(150)
    await A.locator('[data-page=plan] .card:has-text("Test VMA")').screenshot(path='v_card.png')
    # coach pro
    await A.evaluate("setKey('sk-test');renderAll()")
    await A.evaluate("adjWeek()"); await A.wait_for_timeout(500)
    print('adj', await A.evaluate("JSON.stringify(Object.entries(S.adj).map(([k,a])=>[k,a.action]))"), 'log', await A.evaluate("S.adjLog.n+' · '+S.adjLog.resume"))
    print('prompt has perio', 'Périodisation' in calls[-1]['messages'][0]['content'], 'tool', calls[-1]['tools'][0]['name'])
    L=await A.evaluate("JSON.stringify((()=>{const out=[];for(let i=0;i<7;i++){const dt=new Date();dt.setDate(dt.getDate()+i);daySessions(weekIdx(dt),dayIdx(dt)).forEach(o=>{if(o.adj)out.push([o.adj,strip(o.t).slice(0,30),!!o.cancel]);});}return out;})())")
    print('overlay', L)
    print('load cancel', await A.evaluate("(()=>{for(let i=0;i<7;i++){const dt=new Date();dt.setDate(dt.getDate()+i);const c=daySessions(weekIdx(dt),dayIdx(dt)).find(o=>o.cancel);if(c)return planLoad(c,getA().P);}return 'none'})()"), 'ics skips', await A.evaluate("planCalSessions().every(x=>!x.o.cancel)"))
    await A.evaluate("renderAll();showTab('today')"); await A.wait_for_timeout(100); await A.screenshot(path='c_today.png',full_page=True)
    await A.evaluate("showTab('plan')"); await A.wait_for_timeout(100); await A.locator('[data-page=plan] .card.lum').first.screenshot(path='c_perio.png')
    await A.evaluate("adjClear()"); print('cleared', await A.evaluate("Object.values(S.adj).every(a=>a.action==='garder')"), await A.evaluate("(()=>{for(let i=0;i<7;i++){const dt=new Date();dt.setDate(dt.getDate()+i);if(daySessions(weekIdx(dt),dayIdx(dt)).some(o=>o.adj))return false;}return true})()"))
    # auto du dimanche (simulé)
    n=len(calls); await A.evaluate("S.settings.coachWeekly=true;S.adjTag=null;const d=new Date();while(dayIdx(d)!==6)d.setDate(d.getDate()+1);d.setHours(19,0,0,0);window.__d=d;adjAuto(d)"); await A.wait_for_timeout(500)
    print('auto', len(calls)-n, await A.evaluate("S.adjLog.auto"), 'again', await A.evaluate("adjAuto(window.__d);adjBusy"), len(calls)-n); await A.evaluate("window.__now=null")
    # calage du plan sur la course (dans 9 semaines)
    A.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await A.evaluate("const r=new Date();r.setDate(r.getDate()+63);S.race={name:'Trail test',date:iso(r),km:25};save();renderAll()")
    print('race week', await A.evaluate("weekIdx(parseISO(S.race.date))"), 'align btn', await A.evaluate("$('[data-page=plan]').innerText.includes('Caler le plan sur la course')"))
    await A.evaluate("perioAlign()"); print('aligned', await A.evaluate("weekIdx(parseISO(S.race.date))"), await A.evaluate("perioTxt()"))
    # description Strava
    await A.evaluate("S.demo=false;S.tokens={access:'x',refresh:'y',exp:Date.now()/1000+9999,scope:'read,activity:read_all,activity:write'};S.settings.stravaWrite=true;S.settings.stravaName=true")
    k=await A.evaluate("(()=>{const w=Math.max(0,weekIdx()),o=runPlan(w).s[0];S.links[o.k]={src:'strava',id:999,km:8,t:2700};S.descQ=[{id:999,k:o.k}];return o.k})()")
    print('desc txt', await A.evaluate(f"descTxt(planObjOf('{k}'),'{k}')"))
    print('flush', await A.evaluate("stravaDescFlush()"), [(m_,json.loads(b) if b else None) for m_,u,b in strava if m_=='PUT'][:1], 'queue', await A.evaluate("S.descQ.length"))
    await A.evaluate("openSettings()"); print('settings', await A.evaluate("$('#sheetBody').innerText.includes('description de mes sorties Strava')")); await A.evaluate("closeSettings()")
    await A.evaluate("S.tokens.scope='read,activity:read_all';S.descQ=[{id:999,k:'"+k+"'}]"); n=len(strava); print('no scope', await A.evaluate("stravaDescFlush()"), len(strava)-n)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
