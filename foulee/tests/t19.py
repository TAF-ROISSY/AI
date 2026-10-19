"""Coach du jour : moments de la journée, conseils calculés, ressenti, conseil IA (manuel et automatique), carte repliée."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x))); calls=[]
    async def ant(r):
        bd=json.loads(r.request.post_data); calls.append(bd)
        await r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'content':[{'type':'text','text':'Pars sur 45 min en Z2 et garde **2 répétitions** en réserve sur les squats.'}],'stop_reason':'end_turn'}))
    await A.route('https://api.anthropic.com/**',ant)
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.heat=null;S.doneAt={};save();renderAll()"); await A.wait_for_timeout(300)
    at=lambda h: f"(()=>{{const d=new Date();d.setHours({h},0,0,0);return d;}})()"
    # moments sans séance cochée
    for h in [7,14,21]:
        r=await A.evaluate(f"JSON.stringify((()=>{{const C=coachDay({at(h)});return {{m:C.m,lab:C.lab,x:strip(C.x),n:C.p.length,t:C.p.map(p=>strip(p.t))}};}})())")
        print('h',h,r)
    # jour avec séances : vitesse + renfo A aujourd'hui, sortie longue demain
    await A.evaluate("const d=dayIdx();S.sched={...SD(),q:d,A:d,l:(d+1)%7,C:(d+3)%7,B:(d+5)%7};save();renderAll()")
    for h in [7,21]:
        r=await A.evaluate(f"JSON.stringify((()=>{{const C=coachDay({at(h)});return {{m:C.m,x:strip(C.x),t:C.p.map(p=>strip(p.t)),b:C.p.map(p=>p.b&&p.b[0]).filter(Boolean)}};}})())")
        print('sess h',h,r)
    # après séance : on coche la première séance du jour (ou une routine) il y a 30 min
    k=await A.evaluate("(()=>{const ss=daySessions(weekIdx(),dayIdx());return ss.length?ss[0].k:prevObj('core').k;})()")
    await A.evaluate(f"S.done['{k}']=true;S.doneAt={{'{k}':Date.now()-30*60e3}};delete S.fb['{k}'];save();renderAll()")
    r=await A.evaluate("JSON.stringify((()=>{const C=coachDay();return {m:C.m,x:strip(C.x),t:C.p.map(p=>strip(p.t)),btn:C.p.map(p=>p.b&&p.b[1]).filter(Boolean)};})())")
    print('apres', r)
    print('moment now', await A.evaluate("cdjMoment()"), 'key', await A.evaluate("cdjKey()"))
    # sortie Strava terminée il y a 1 h → après séance aussi
    await A.evaluate("S.doneAt={};const r=S.activities.find(a=>a.type==='Run'||a.sport_type==='TrailRun'||a.sport_type==='Run');const st=new Date(Date.now()-3600e3-(r.elapsed_time||r.moving_time)*1000);const pad=n=>String(n).padStart(2,'0');window.__run={...r,id:999001,name:'Test crête',start_date_local:`${st.getFullYear()}-${pad(st.getMonth()+1)}-${pad(st.getDate())}T${pad(st.getHours())}:${pad(st.getMinutes())}:00Z`};S.activities.unshift(window.__run);A=null;save();renderAll()")
    r=await A.evaluate("JSON.stringify((()=>{const C=coachDay();return {m:C.m,x:strip(C.x),t:C.p.map(p=>strip(p.t))};})())")
    print('apres run', r)
    # carte affichée sur les 3 accueils
    for mod,tab in [['trail','trail'],['muscu','muscu'],['cross','cross']]:
        await A.evaluate(f"setMod('{mod}','{tab}')"); await A.wait_for_timeout(120)
        print('card',tab, await A.evaluate(f"!!document.querySelector('[data-page={tab}] details.cdj[open]')"))
    await A.evaluate("setMod('trail','trail')"); await A.wait_for_timeout(150)
    await A.screenshot(path='k_cdj.png')
    # repli = vu jusqu'au prochain moment
    await A.evaluate("document.querySelector('[data-page=trail] details.cdj summary').click()"); await A.wait_for_timeout(150)
    print('seen', await A.evaluate("S.cdjSeen===cdjKey()"), 'closed after render', await A.evaluate("renderAll();!document.querySelector('[data-page=trail] details.cdj').open"))
    # sans clé : bouton d'activation
    print('no key btn', await A.evaluate("document.querySelector('[data-page=trail] details.cdj').textContent.includes('Activer le coach')"))
    # conseil IA manuel
    await A.evaluate("localStorage.setItem('foulee_api','sk-test');S.cdjSeen=null;renderAll()")
    await A.evaluate("cdjAI()"); await A.wait_for_timeout(600)
    print('ai', len(calls), await A.evaluate("S.cdj&&S.cdj.k===cdjKey()"), await A.evaluate("document.querySelector('[data-page=trail] .cdj-ai').innerText"))
    u=calls[-1]['messages'][0]['content']; print('prompt', u[:90].replace('\n',' '), '| ctx' , 'Données actuelles' in calls[-1]['system'], calls[-1]['max_tokens'])
    await A.wait_for_timeout(2600); await A.locator('[data-page=trail] details.cdj').screenshot(path='k_cdj_ai.png')
    # automatique : un seul appel par moment
    await A.evaluate("S.cdj=null;S.cdjFail=null;S.settings.cdjAuto=true;save()"); n0=len(calls)
    await A.evaluate("cdjTick()"); await A.wait_for_timeout(500); await A.evaluate("cdjTick();cdjAuto()"); await A.wait_for_timeout(500)
    print('auto calls', len(calls)-n0)
    # erreur API : pas de boucle
    await A.unroute('https://api.anthropic.com/**'); n1=len(calls)
    async def ko(r): calls.append(1); await r.fulfill(status=529,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"error":{"message":"overloaded"}}')
    await A.route('https://api.anthropic.com/**',ko)
    await A.evaluate("S.cdj=null;S.cdjFail=null;save();cdjAuto()"); await A.wait_for_timeout(500); await A.evaluate("cdjAuto();cdjAuto()"); await A.wait_for_timeout(300)
    print('fail calls', len(calls)-n1, 'fail key', await A.evaluate("S.cdjFail===cdjKey()"))
    # réglage et en parler
    await A.evaluate("openSettings()"); await A.wait_for_timeout(100); print('setting', await A.evaluate("document.querySelector('#s_cdj').checked"))
    await A.evaluate("closeSettings();cdjAsk()"); await A.wait_for_timeout(100); print('ask', await A.evaluate("$('#chatIn').value.slice(0,40)"))
    await A.evaluate("closeCoach()")
    print('nosync', await A.evaluate("JSON.stringify(Object.keys(syncPayload().data).filter(k=>/^cdj/.test(k)))"))
    for t in [['trail','trail'],['muscu','muscu'],['cross','cross'],['cross','forme']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
