"""v8.9 : suivi de trace à la voix (montées / descentes annoncées, sommet, ravito, écart au plan, hors trace) et mode jour J (semaine de course, checklist, temps de passage, récupération appliquée au plan, résultat)."""
import os, json, math
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;window._dn=Date.now.bind(Date);const _dn=window._dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
# trace : 6 km vers le nord ; montée de 1 km à 10 % entre 1,5 et 2,5 km, descente 3–3,8 km
def gpx_pts():
    pts=[];lat0,lon=45.9,6.1
    for i in range(0,6001,25):
        d=i; z=500
        if 1500<=d<2500: z=500+(d-1500)*.10
        elif 2500<=d<3000: z=600
        elif 3000<=d<3800: z=600-(d-3000)*.10
        elif d>=3800: z=520
        pts.append([lat0+d/111320,lon,z,d])
    return pts
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    pts=json.dumps(gpx_pts())
    await A.evaluate(f"(()=>{{const d=new Date();d.setDate(d.getDate()+3);S.race={{name:'Trail des Crêtes',date:iso(d),km:6,dp:100,aid:[4.2],gpx:{{pts:{pts}}}}};save();renderAll();}})()")
    R=await A.evaluate("JSON.stringify((()=>{const r=routeBuild(S.race.gpx.pts.map(p=>[p[0],p[1],p[2]]));return {len:Math.round(r.len),segs:r.segs.map(s=>[s.up,Math.round(s.a),Math.round(s.b),s.gain,Math.round(s.g*100)])}})())"); print('route', R)
    print('srcs', await A.evaluate("routeSrcs().map(x=>x.id).join(',')"))
    await A.evaluate("routeOpen('race')"); print('open', await A.evaluate("JSON.stringify({steps:GR.steps.length,d:Math.round(GR.steps[0].d),plan:!!GR.route.plan,aid:GR.route.aid})"))
    await A.evaluate("window.__now=_dn();window.__said=[];grStart();window.__said=[]")
    # course le long de la trace à 3 m/s, avec un écart de 90 m entre 4,5 et 4,9 km
    await A.evaluate("""(()=>{let t=window.__now;for(let d=10;d<=6000;d+=9){t+=3000;window.__now=t;const off=(d>4500&&d<4900)?90/(111320*Math.cos(45.9*Math.PI/180)):0;grFeed({t,lat:45.9+d/111320,lon:6.1+off,acc:5});if(d%27===0)grTick();}})()""")
    s=await A.evaluate("window.__said")
    for k in ['Montée dans','Sommet','Descente dans','Ravitaillement','Trace : kilomètre','éloignes','retour sur la trace']:
        hit=[x for x in s if k in x]; print('said', k, len(hit), (hit[0][:90] if hit else ''))
    await A.locator('#grv').screenshot(path='rt_run.png'); await A.evaluate("grStop(false);$('#grv').classList.remove('on');window.__now=null")
    # jour J
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(150); print('week card', await A.evaluate("$('[data-page=today]').innerText.includes('Semaine de course')"))
    await A.evaluate("openRaceDay()"); await A.wait_for_timeout(150)
    print('sheet', await A.evaluate("$('#sheetBody .rd-cd').textContent"), 'kit', await A.evaluate("document.querySelectorAll('#sheetBody .rd-kit input').length"), 'passages', await A.evaluate("document.querySelectorAll('#sheetBody .tbl tr').length"), 'guided btn', await A.evaluate("$('#sheetBody').innerText.includes('Course guidée sur la trace')"))
    await A.locator('#sheetBody .rd-kit input').nth(0).click(); await A.wait_for_timeout(100); print('kit saved', await A.evaluate("JSON.stringify(Object.values(S.rdKit)[0])"))
    await A.screenshot(path='rd_sheet.png',full_page=True); await A.evaluate("closeSettings()")
    # après la course : J+2 → séances adaptées
    await A.evaluate("(()=>{const d=new Date();d.setDate(d.getDate()-2);S.race.date=iso(d);save();renderAll();})()")
    print('rec card', await A.evaluate("$('[data-page=today]').innerText.includes('Récupération')"), await A.evaluate("recPlan(2)[0]"))
    print('overlay', await A.evaluate("(()=>{const out=[];for(let i=0;i<3;i++){const dt=new Date();dt.setDate(dt.getDate()+i);daySessions(weekIdx(dt),dayIdx(dt)).forEach(o=>{if(!S.done[o.k])out.push([i,strip(o.t).slice(0,30),!!o.cancel,!!o.rec]);});}return JSON.stringify(out)})()"))
    print('in 5 days', await A.evaluate("(()=>{const dt=new Date();dt.setDate(dt.getDate()+5);return JSON.stringify(daySessions(weekIdx(dt),dayIdx(dt)).map(o=>!!o.rec))})()"))
    await A.evaluate("openRaceResult()"); await A.fill('#rr_t','0:42'); await A.fill('#rr_p','12 / 300'); await A.locator('#sheetBody button:has-text("Enregistrer")').click(); await A.wait_for_timeout(100)
    print('result', await A.evaluate("JSON.stringify(S.races.find(x=>x.n==='Trail des Crêtes'))"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
