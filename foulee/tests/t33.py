"""v8.1 : autres sports — choix des sports, semaine type (Plan › Autres sports), séances dans Aujourd’hui / Semaine / calendrier, coche = saisie, rattachement Strava, stats 4 semaines, synchro et suppressions."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll();showTab('sports')"); await A.wait_for_timeout(200)
    print('sub', await A.evaluate("[...document.querySelectorAll('#modSeg button')].map(b=>b.textContent).join('|')"))
    print('default sports', await A.evaluate("mySports().join(',')"), 'catalogue', await A.evaluate("Object.keys(XTYPES).length"))
    await A.locator('[data-page=sports] .chip:has-text("Rameur")').click(); await A.locator('[data-page=sports] .chip:has-text("Randonnée")').click()
    print('toggled', await A.evaluate("mySports().join(',')"))
    # séance vélo le jour J, natation demain
    d=await A.evaluate("dayIdx()")
    await A.locator('[data-page=sports] button:has-text("Séance")').click(); await A.wait_for_timeout(100)
    await A.select_option('#xp_day',str(d)); await A.fill('#xp_min','90'); await A.fill('#xp_km','40'); await A.fill('#xp_note','sortie club')
    await A.locator('#sheetBody .chip:has-text("Tempo")').click(); await A.locator('#sheetBody button:has-text("Enregistrer")').click(); await A.wait_for_timeout(100)
    await A.evaluate(f"openXPlan();XP.type='nat';renderXPlan(false)"); await A.select_option('#xp_day',str((d+1)%7)); await A.fill('#xp_min','45'); await A.fill('#xp_km','1500'); await A.locator('#sheetBody button:has-text("Enregistrer")').click(); await A.wait_for_timeout(100)
    print('xplan', await A.evaluate("JSON.stringify(S.xplan.map(p=>[p.type,p.day,p.min,p.int,p.km,p.note]))"))
    await A.screenshot(path='x_sports.png',full_page=True)
    print('today', await A.evaluate("$('[data-page=today]').innerText.includes('Vélo route ·')"), 'dot x', await A.evaluate("document.querySelectorAll('[data-page=today] .dot.x').length"))
    print('cross', await A.evaluate("document.querySelectorAll('[data-page=cross] .xc.xo').length"))
    print('load', await A.evaluate("Math.round(planLoad(daySessions(weekIdx(),dayIdx(),'x')[0],getA().P))"), 'kinds', await A.evaluate("[daySessions(weekIdx(),dayIdx(),'run').every(s=>!s.xs),daySessions(weekIdx(),dayIdx(),'str').every(s=>s.str)].join(',')"))
    # calendrier
    print('ics', await A.evaluate("PCD.from='now';(()=>{const L=planCalSessions();return [L.filter(x=>x.xs).length, planIcs(L).includes('Natation')]})()"), 'filter off', await A.evaluate("PCD.x=false;const n=planCalSessions().filter(x=>x.xs).length;PCD.x=true;n"))
    # coche → saisie
    k=await A.evaluate("daySessions(weekIdx(),dayIdx(),'x')[0].k")
    await A.evaluate("showTab('today')"); await A.evaluate(f"toggleDone('{k}')"); await A.wait_for_timeout(100)
    print('ticked', await A.evaluate(f"S.done['{k}']"), 'xact', await A.evaluate(f"JSON.stringify((S.xact||[]).filter(x=>x.id==='p{k}').map(x=>[x.type,x.min,x.rpe,x.km]))"), 'sheet', await A.evaluate("$('#sheetBody').innerText.includes('Modifier une activité')"))
    await A.evaluate("closeSettings()"); await A.evaluate(f"toggleDone('{k}')"); print('unticked', await A.evaluate(f"S.done['{k}']"), await A.evaluate(f"(S.xact||[]).some(x=>x.id==='p{k}')"), 'tomb', await A.evaluate(f"S.del.xact.includes('p{k}')"))
    # Strava : vélo du jour → coché et lié, pas de doublon
    await A.evaluate("""(()=>{const n=new Date(),p=x=>String(x).padStart(2,'0'),dd=`${n.getFullYear()}-${p(n.getMonth()+1)}-${p(n.getDate())}T07:00:00Z`;S.activities.push({id:888001,name:'Gravel du matin',sport_type:'GravelRide',start_date_local:dd,distance:42300,moving_time:5400,total_elevation_gain:320,average_heartrate:132});save();})()""")
    print('linked', await A.evaluate("linkPlan(true)"), await A.evaluate(f"JSON.stringify(S.links['{k}'])"), 'done', await A.evaluate(f"S.done['{k}']"))
    print('once', await A.evaluate(f"xactAll().filter(x=>x.id==='s888001'||x.id==='p{k}').length"), 'again', await A.evaluate("linkPlan(true)"))
    await A.evaluate("renderAll();showTab('sports')"); await A.wait_for_timeout(100)
    print('stats', await A.evaluate("JSON.stringify(Object.fromEntries(Object.entries(sportsStats()).map(([k,b])=>[k,[b.n,Math.round(b.min),Math.round(b.km)]])))"), 'speed', await A.evaluate("xSpeed('velo',42.3,90)"), await A.evaluate("xSpeed('nat',1.5,30)"))
    await A.screenshot(path='x_sports2.png',full_page=True)
    # coach + synchro + suppression
    print('coach ctx', await A.evaluate("JSON.stringify(coachCtx?coachCtx().autres_sports_prevus:null)") if await A.evaluate("typeof coachCtx==='function'") else 'n/a')
    print('synced', await A.evaluate("'xplan' in syncPayload().data"))
    pid=await A.evaluate("S.xplan.find(p=>p.type==='nat').id")
    await A.evaluate(f"openXPlan('{pid}')"); A.on('dialog',lambda dlg: asyncio.ensure_future(dlg.accept()))
    await A.locator('#sheetBody button:has-text("Supprimer")').click(); await A.wait_for_timeout(150)
    print('deleted', await A.evaluate("S.xplan.length"), await A.evaluate(f"S.del.xplan.includes('{pid}')"))
    await A.evaluate(f"S.xplan.push({{id:'{pid}',type:'nat',day:1,min:30,int:'e'}});applyTomb()"); print('tomb ok', await A.evaluate("S.xplan.length"))
    # non sélectionné → pas importé
    await A.evaluate("S.activities.push({id:888002,name:'Kayak',sport_type:'Kayaking',start_date_local:'2026-10-18T09:00:00Z',distance:8000,moving_time:3600});"); print('kayak hidden', await A.evaluate("!xactAll().some(x=>x.id==='s888002')"))
    await A.evaluate("xToggleSport('kayak')"); print('kayak shown', await A.evaluate("xactAll().some(x=>x.id==='s888002')"))
    for t in ['today','plan','renfo','sports','cross','forme']:
        await A.evaluate(f"showTab('{t}')"); await A.wait_for_timeout(40)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
