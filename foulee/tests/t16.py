import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();save()"); await A.wait_for_timeout(300)
    print('cf0', await A.evaluate("JSON.stringify((({ql,gl,q,g,R})=>({ql,gl,q:+q.toFixed(1),g:+g.toFixed(1),n:R.length}))(crossFatigue()))"))
    # add a big downhill run 20 h ago
    await A.evaluate("""(()=>{const d=new Date(Date.now()-20*36e5);const pad=n=>String(n).padStart(2,'0');const s=`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00Z`;S.activities.push({id:999001,name:'Grand trail test',sport_type:'TrailRun',start_date_local:s,distance:24000,moving_time:3*3600,total_elevation_gain:1100,average_heartrate:148,poly:''});A=null;save();})()""")
    print('cf1', await A.evaluate("JSON.stringify((({ql,gl,q,g})=>({ql,gl,q:+q.toFixed(1),g:+g.toFixed(1)}))(crossFatigue()))"))
    r=await A.evaluate("""(()=>{const w=Math.max(0,weekIdx());const T=adaptSession({...strSession('A',w),when:new Date()});return JSON.stringify({notes:T.notes,items:T.items.map(i=>i.id+(i.from?'<-'+i.from+'('+i.why+')':'')+' '+i.p)})})()""")
    print('adaptA', r)
    r=await A.evaluate("""(()=>{const w=Math.max(0,weekIdx());const T=adaptSession({...strSession('A',w),when:new Date(Date.now()+4*86400e3)});return JSON.stringify(T.items.map(i=>i.id))})()""")
    print('future (no cf)', r)
    # taper
    await A.evaluate("S.race={name:'Trail X',date:iso(new Date(Date.now()+2*86400e3)),km:30,dp:1500,aid:[]};save()")
    print('taper', await A.evaluate("JSON.stringify(taperFor(new Date()))"))
    r=await A.evaluate("""(()=>{const w=Math.max(0,weekIdx());const T=adaptSession({...strSession('B',w),when:new Date()});return JSON.stringify({n:T.notes,p:T.items.map(i=>i.id+' '+i.p)})})()""")
    print('taperB', r)
    await A.evaluate("S.race=null;save();setMod('muscu','muscu')"); await A.wait_for_timeout(300)
    await A.screenshot(path='h_home.png',full_page=True)
    print('reco', await A.evaluate("JSON.stringify(prevReco(crossFatigue(),null))"))
    # feedback sliders
    await A.evaluate("openMuscuFb({type:'sess',k:'s0A'},'Comment c’était ?')"); await A.wait_for_timeout(100)
    await A.screenshot(path='h_fb.png')
    await A.evaluate("mfb.sore.legs=3;mfb.rpe=8;saveMuscuFb()"); print('fb saved', await A.evaluate("JSON.stringify(S.fb.s0A)"))
    await A.evaluate("S.activities=S.activities.filter(a=>a.id!==999001);A=null;"); print('cf from soreness', await A.evaluate("crossFatigue().ql"))
    # hybrid
    print('hybrid', await A.evaluate("JSON.stringify(hybridAt(new Date()))"))
    await A.evaluate("setMod('cross','cross')"); await A.wait_for_timeout(300); await A.screenshot(path='h_cross.png')
    # routines in Séances
    await A.evaluate("setMod('muscu','renfo')"); await A.wait_for_timeout(200)
    print('routines', await A.evaluate("['Pied & Cheville','Descente blindée','Core & Posture'].map(t=>document.querySelector('[data-page=renfo]').innerText.includes(t))"))
    # imports
    await A.evaluate("setMod('trail','analyse')"); await A.wait_for_timeout(200)
    await A.set_input_files('[data-page=analyse] input[type=file]',os.path.join(AS,'test_run.fit')); await A.wait_for_timeout(1200)
    print('fit', await A.evaluate("JSON.stringify((S.imports||[]).map(r=>({n:r.name,km:+r.km.toFixed(2),up:r.up,dn:r.dn,mov:r.mov,hr:r.hr,cad:r.cad,pts:r.s.d.length})))"))
    await A.screenshot(path='h_fit.png',full_page=True)
    print('diag', await A.evaluate("JSON.stringify((()=>{const r=S.imports[0],D=diagRun(r.s,r.km,r.dn);return {bins:D.bins&&D.bins.map(b=>b.l+':'+(b.dd/1000).toFixed(1)+':'+(b.ratio&&b.ratio.toFixed(2))),drift:D.drift,rec:D.rec.map(x=>x.t)}})())"))
    await A.evaluate("closeSettings()")
    await A.set_input_files('[data-page=analyse] input[type=file]',os.path.join(AS,'test_run.gpx')); await A.wait_for_timeout(1200)
    print('gpx', await A.evaluate("JSON.stringify((S.imports||[]).map(r=>({n:r.name,km:+r.km.toFixed(2),up:r.up,dn:r.dn,mov:r.mov,hr:r.hr})))"))
    print('cf with import', await A.evaluate("JSON.stringify((({ql,gl,R})=>({ql,gl,R:R.map(r=>r.name)}))(crossFatigue()))"))
    # renderAct diag with demo
    await A.evaluate("closeSettings();openAct(S.activities.find(a=>a.poly).id)"); await A.wait_for_timeout(1500)
    print('act diag', await A.evaluate("document.querySelector('#actBody').innerText.includes('Diagnostic pente')"))
    print('ctx', await A.evaluate("JSON.stringify({f:coachContext().fatigue_croisee.quadriceps,s:coachContext().score_polyvalence,i:coachContext().fichiers_importes.length})"))
    await A.evaluate("closeAct();openCtx()"); await A.wait_for_timeout(100); print('tfl chip', await A.evaluate("document.querySelector('#sheetBody').innerText.includes('TFL')"))
    for t in ['muscu','renfo','figures','defis','suivi','chrono']:
        await A.evaluate(f"closeSettings();setMod('muscu','{t}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
