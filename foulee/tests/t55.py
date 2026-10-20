"""v10.3 : encouragements en direct (Foulée Suivi → serveur → voix du coureur), brief du matin (carte, voix, #brief, version coach), forme le jour J (modèle forme / fatigue, affûtage, « et si »), trail mythique virtuel (choix, progression, étapes franchies, carte, famille)."""
import os, json, subprocess, time
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
ME='e'*32; CH=[]; NOW=int(time.time()*1000)
LIVE={'v':1,'pseudo':'Christophe','st':'run','name':'Footing','t0':NOW-600e3,'upd':NOW,'el':600,'dist':2000,'pos':[45.9,6.1],'trk':[[45.9,6.1]],'sos':False}
async def push(route):
    r=route.request;u=r.url
    if '/cheer' in u and r.method=='POST': b=json.loads(r.post_data); b['id']=int(time.time()*1000); CH.append(b); await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"ok":true}');return
    if '/cheer' in u:
        since=int((u.split('since=')+['0'])[1].split('&')[0] or 0); await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'list':[c for c in CH if c['id']>since]}));return
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"ok":true}')
async def gh(route):
    r=route.request
    if r.method in ('POST','PATCH'): await route.fulfill(status=200,content_type='application/json',body=json.dumps({'id':ME}));return
    LIVE['upd']=int(time.time()*1000); await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'files':{'foulee-live.json':{'content':json.dumps(LIVE)}}}))
async def claude(route):
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"text","text":"Salut Christophe, belle forme ce matin : profite de ta séance, et pense à bien boire."}],"stop_reason":"end_turn"}))
async def setup(pg):
    await pg.add_init_script(INIT); await pg.route('https://fonts.**',lambda r:r.abort()); await pg.route('https://push.test/**',push); await pg.route('https://api.github.com/**',gh); await pg.route('https://api.anthropic.com/**',claude); await pg.route('https://cdnjs.cloudflare.com/**',lambda r:r.abort()); await pg.route('https://*open-meteo.com/**',lambda r:r.abort())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]; ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append('A '+str(x))); await setup(A)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate(f"loadDemo();setVC({{token:'ghp'}});S.settings.pushUrl='https://push.test';S.settings.live=true;S.liveGist='{ME}';S.briefSeen=null;save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    # --- brief
    print('brief', await A.evaluate("$('[data-page=today] .brief')?$('[data-page=today] .brief p').textContent.slice(0,160):(new Date().getHours()<4||new Date().getHours()>=14?'(hors horaire)':'none')"))
    print('brief data', await A.evaluate("briefData().txt.slice(0,140)"))
    await A.evaluate("window.__said=[];briefSpeak()"); print('brief voice', await A.evaluate("window.__said.join(' ').slice(0,80)"))
    await A.evaluate("setKey('sk-ant-x');S.settings.briefAI=true;save();briefAI(true)"); await A.wait_for_timeout(500); print('brief ai', await A.evaluate("S.brief&&S.brief.ai"))
    await A.evaluate("window.__said=[];location.hash='brief'"); await A.wait_for_timeout(1500); print('hash brief', await A.evaluate("window.__said.length>0"), await A.evaluate("location.hash===''"))
    # --- forme J
    await A.evaluate("(()=>{const d=new Date();d.setDate(d.getDate()+10);S.race={name:'Trail des Crêtes',date:iso(d),km:30,dp:1500};save();showTab('courses');renderCourses()})()"); await A.wait_for_timeout(600)
    print('race now', await A.evaluate("JSON.stringify(S.race)")); print('bm', await A.evaluate("$('[data-page=courses] .bm')?$('[data-page=courses] .bm').innerText.replace(/\\n/g,' ').slice(0,200):'none'"))
    M=await A.evaluate("JSON.stringify((({sc,pct,lab,C})=>({sc,pct:Math.round(pct),lab,C:Math.round(C)}))(bmModel(bmTarget())))"); print('model', M)
    await A.locator('[data-page=courses] .bm').screenshot(path='v103_bm.png')
    print('taper btn', await A.evaluate("!![...document.querySelectorAll('[data-page=courses] .bm button')].find(b=>b.textContent.includes('affûtage'))"))
    n0=await A.evaluate("Object.keys(S.adj||{}).length"); await A.evaluate("bmTaper()"); print('taper adj', n0, '→', await A.evaluate("Object.keys(S.adj||{}).length"), 'after', await A.evaluate("JSON.stringify((({sc,pct})=>({sc,pct:Math.round(pct)}))(bmModel(bmTarget())))"))
    await A.evaluate("BMX=[{d:iso(new Date(Date.now()+5*864e5)),l:900}];renderCourses()"); await A.wait_for_timeout(300); print('what-if', await A.evaluate("$('[data-page=courses] .bm details').innerText.includes('séance ajoutée')"), await A.evaluate("JSON.stringify((({sc,pct})=>({sc,pct:Math.round(pct)}))(bmModel(bmTarget(),BMX)))")); await A.evaluate("BMX=[]")
    # --- trail virtuel
    await A.evaluate("openVtr()"); print('vtr list', await A.evaluate("document.querySelectorAll('#sheetBody .run').length"))
    await A.evaluate("vtrStart('utmb',false);S.vtrail.start=iso(new Date(Date.now()-60*864e5));S.vtrail.passed=1;save();closeSettings();showTab('today');renderToday()"); await A.wait_for_timeout(600)
    print('vtr', await A.evaluate("JSON.stringify((({km,dp,f,pass,next})=>({km:Math.round(km),dp:Math.round(dp),f:Math.round(f*100),pass:pass.length,next:next&&next[0]}))(vtrState()))"))
    print('vtr card', await A.evaluate("$('[data-page=today] .vtr')?$('[data-page=today] .vtr').innerText.replace(/\\n/g,' '):'none'"), 'passed saved', await A.evaluate("S.vtrail.passed"))
    await A.locator('[data-page=today] .vtr').screenshot(path='v103_vtr.png')
    await A.evaluate("openVtr()"); await A.wait_for_timeout(300); print('vtr sheet', await A.evaluate("document.querySelectorAll('#sheetBody .vtr-w .ok').length"), await A.evaluate("!!$('#vtrMap')")); await A.screenshot(path='v103_vtrsheet.png',full_page=True); await A.evaluate("closeSettings()")
    # --- encouragements
    W=await ctx.new_page(); W.on('pageerror',lambda x:errs.append('W '+str(x))); await setup(W)
    await W.goto(f'http://127.0.0.1:8765/suivi.html#add={ME}&n=Christophe|push=https%3A%2F%2Fpush.test'); await W.wait_for_timeout(1000)
    k=await A.evaluate("(()=>{for(let w=0;w<12;w++)for(let d=0;d<7;d++){const o=daySessions(w,d,'run').find(x=>/e$/.test(x.k));if(o)return o.k;}})()")
    await A.evaluate(f"grOpen('{k}')"); await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(500)
    await W.locator('button:has-text("Encourager")').click(); await W.fill('#cme','Maman'); await W.locator('#shb .btn:has-text("Allez")').click(); await W.wait_for_timeout(500)
    print('cheer sent', len(CH), CH[-1] if CH else '', await W.evaluate("window.__cheer"))
    await A.evaluate("window.__said=[];cheerTick(true)"); await A.wait_for_timeout(600); await A.wait_for_timeout(1500);print('runner heard (auto)', await A.evaluate("JSON.stringify((GR.cheers||[]).map(c=>c.from+': '+c.text))"), await A.evaluate("window.__said.filter(x=>x.startsWith('Message de')).join(' / ')"));print('say fmt', await A.evaluate("cheerSay({from:'Maman',text:'Allez ! 👏💪'})"));print('runner heard', await A.evaluate("window.__said.join(' / ')"))
    await A.evaluate("window.__said=[];cheerTick(true)"); await A.wait_for_timeout(400); print('no repeat', await A.evaluate("window.__said.length===0"))
    await A.evaluate("grStop(false);$('#grv').classList.remove('on')")
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
