import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, subprocess, time, base64
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,accept_downloads=True)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.done.s0A=true;S.mesures.push({d:'2026-10-01',p:80,t:90});S.settings.fcrest=50;S.settings.fcmax=185;save();renderAll()"); await A.wait_for_timeout(300)
    # settings
    await A.evaluate("openSettings()"); await A.wait_for_timeout(600)
    print('sto', await A.evaluate("document.querySelector('#stoLine').innerText"))
    async with A.expect_download() as dl: await A.evaluate("exportData()")
    d=await dl.value; path='bk.json'; await d.save_as(path); bk=json.load(open(path)); print('export', d.suggested_filename, bk['app'], bk['version'], 'done' in bk['S'], bk['S'].get('tokens'))
    # corrupt restore
    open('bad.json','w').write('{"foo":1}')
    A.on('dialog', lambda dg: asyncio.ensure_future(dg.accept('EFFACER') if dg.type=='prompt' else dg.accept()))
    await A.set_input_files('#sheetBody input[type=file][accept^=".json"]','bad.json'); await A.wait_for_timeout(400)
    print('toast bad', await A.evaluate("document.querySelector('.toast,#toast')&&document.querySelector('.toast,#toast').innerText"))
    await A.evaluate("S.done={};S.mesures=[];save()")
    await A.evaluate("openSettings()"); await A.wait_for_timeout(200)
    await A.set_input_files('#sheetBody input[type=file][accept^=".json"]',path); await A.wait_for_timeout(600)
    print('restored', await A.evaluate("JSON.stringify({d:S.done.s0A,m:S.mesures.length,acts:S.activities.length})"))
    # cache
    await A.evaluate("localStorage.setItem('foulee_act_1','{}');localStorage.setItem('foulee_act_2','{}');openSettings();clearActCache()"); print('cache left', await A.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('foulee_act_')).length"))
    # zones
    print('zones', await A.evaluate("JSON.stringify(hrZ())"))
    await A.evaluate("closeSettings();setMod('trail','plan')"); await A.wait_for_timeout(200)
    print('plan zones', await A.evaluate("document.querySelector('[data-page=plan]').innerText.includes('Zones cardiaques')"))
    await A.evaluate("openAct(S.activities.find(a=>a.poly&&a.average_heartrate).id)"); await A.wait_for_timeout(1200)
    print('act zones', await A.evaluate("document.querySelector('#actBody').innerText.includes('Temps par zone')"))
    await A.evaluate("closeAct()")
    # workout export
    k=await A.evaluate("(()=>{for(let w=0;w<12;w++){const s=runPlan(w).s.find(x=>x.wk&&x.wk.work.d);if(s){viewWeek=w;sessCard(s);return s.k;}}})()")
    print('wk key', k)
    await A.evaluate(f"openWkExport('{k}')"); await A.wait_for_timeout(200); await A.screenshot(path='i_wk.png')
    async with A.expect_download() as dl: await A.evaluate(f"wkDl('{k}','fit')")
    d=await dl.value; await d.save_as('wk.fit'); print('fit file', d.suggested_filename)
    async with A.expect_download() as dl: await A.evaluate(f"wkDl('{k}','tcx')")
    d=await dl.value; await d.save_as('wk.tcx')
    k2=await A.evaluate("(()=>{for(let w=0;w<12;w++){const s=runPlan(w).s.find(x=>x.wk&&!x.wk.work.d&&!x.wk.work.p);if(s){sessCard(s);return s.k;}}})()")
    async with A.expect_download() as dl: await A.evaluate(f"wkDl('{k2}','fit')")
    d=await dl.value; await d.save_as('wk2.fit')
    # xact
    await A.evaluate("setMod('cross','cross')"); await A.wait_for_timeout(200)
    await A.evaluate("openXact()"); await A.wait_for_timeout(100); await A.screenshot(path='i_xact.png')
    await A.evaluate("XD.type='rando';document.querySelector('#x_min').value='180';document.querySelector('#x_dp').value='900';document.querySelector('#x_km').value='14';XD.rpe=6;saveXact()")
    await A.evaluate("S.activities.push({id:777,name:'Sortie vélo',sport_type:'Ride',start_date_local:new Date(Date.now()-2*864e5).toISOString().slice(0,19)+'Z',distance:40000,moving_time:5400,total_elevation_gain:300,average_heartrate:130});A=null;renderAll()")
    print('xact', await A.evaluate("JSON.stringify(xactAll().map(x=>[x.type,x.src,Math.round(x.min),x.rpe,Math.round(xLoad(x))]))"))
    print('loads', await A.evaluate("JSON.stringify(loadsBetween(new Date(Date.now()-7*864e5),new Date()))"))
    print('cf rando', await A.evaluate("JSON.stringify(crossFatigue().R.map(r=>r.name+':'+Math.round(r.dn)))"))
    print('runs unaffected', await A.evaluate("getA().runs.some(r=>r.id===777)"))
    await A.screenshot(path='i_cross.png',full_page=True)
    await A.evaluate("setMod('cross','forme')"); await A.wait_for_timeout(200)
    print('ctx', await A.evaluate("JSON.stringify({z:coachContext().zones_fc,x:coachContext().autres_sports_28j.length})"))
    for t in [['trail','trail'],['trail','histo'],['trail','analyse'],['muscu','muscu'],['muscu','renfo'],['muscu','suivi'],['cross','cross']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    # reset
    await A.evaluate("IDB.put({id:1,d:'2026-10-01',front:'x'})"); await A.wait_for_timeout(200)
    await A.evaluate("openSettings();resetApp()"); await A.wait_for_timeout(2500)
    print('after reset', await A.evaluate("JSON.stringify({ls:Object.keys(localStorage).filter(k=>k.startsWith('foulee')&&k!=='foulee_v1'),done:Object.keys(S.done).length,acts:S.activities.length})"))
    print('idb', await A.evaluate("IDB.all().then(a=>a.length)"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
