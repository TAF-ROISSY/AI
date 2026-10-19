"""v6.7 : sommeil (saisie, effet sur la forme et le Coach du jour, synchro), projection du ratio 7 j / 28 j, étoiles de la semaine et badges de bloc."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.heat=null;S.sleep={};const d=dayIdx();S.sched={...SD(),q:d,A:d,l:(d+1)%7,C:(d+3)%7,B:(d+5)%7};save();renderAll()"); await A.wait_for_timeout(300)
    base=await A.evaluate("readiness().sc"); print('forme sans nuit', base)
    # Coach du jour le matin propose de noter la nuit
    print('cdj prompt', await A.evaluate("(()=>{const d=new Date();d.setHours(7,0,0,0);return coachDay(d).p.map(p=>strip(p.t)).join(' | ');})()"))
    # saisie via la feuille
    await A.evaluate("openSleep()"); await A.wait_for_timeout(100)
    await A.evaluate("[...document.querySelectorAll('#sheetBody .chip')].find(b=>b.textContent.trim()==='5 h').click()"); await A.wait_for_timeout(50)
    await A.evaluate("[...document.querySelectorAll('#sheetBody .fbb button')][1].click()"); await A.wait_for_timeout(50)
    await A.screenshot(path='l_sleep_sheet.png')
    await A.evaluate("saveSleep()"); await A.wait_for_timeout(100)
    print('saved', await A.evaluate("JSON.stringify(sleepOf(iso(new Date())))".replace('JSON.stringify(sleepOf(iso(new Date())))','(()=>{const x=sleepOf(iso(new Date()));return JSON.stringify({h:x.h,q:x.q});})()')))
    print('forme nuit courte', await A.evaluate("readiness().sc"), await A.evaluate("readiness().why.slice(-1)[0]"))
    print('cdj nuit courte', await A.evaluate("(()=>{const d=new Date();d.setHours(7,0,0,0);return strip(coachDay(d).x);})()"))
    # très courte, bonne nuit, dette
    for h,q in [[4.5,3],[7.5,4]]:
        await A.evaluate(f"S.sleep[iso(new Date())]={{h:{h},q:{q},t:Date.now()}};save()")
        print('nuit',h,q, await A.evaluate("readiness().sc"), await A.evaluate("JSON.stringify(sleepEffect())"))
    await A.evaluate("const y=n=>iso(new Date(Date.now()-n*864e5));S.sleep[y(1)]={h:5.5,q:3,t:1};S.sleep[y(2)]={h:5,q:3,t:1};S.sleep[iso(new Date())]={h:6.5,q:3,t:2};save()")
    print('dette', await A.evaluate("JSON.stringify(sleepEffect())"))
    # synchro : suppression propagée, puis re-saisie conservée
    await A.evaluate("slDraft={d:iso(new Date(Date.now()-864e5))};delSleep()")
    print('tomb', await A.evaluate("JSON.stringify({del:S.del.sleep.length,gone:!sleepOf(iso(new Date(Date.now()-864e5)))})"))
    await A.evaluate("S.sleep[iso(new Date(Date.now()-864e5))]={h:6,q:2,t:3};applyTomb()"); print('applyTomb removes', await A.evaluate("!sleepOf(iso(new Date(Date.now()-864e5)))"))
    await A.evaluate("slDraft={d:iso(new Date(Date.now()-864e5)),h:6,q:2};saveSleep();applyTomb()"); print('resaved kept', await A.evaluate("!!sleepOf(iso(new Date(Date.now()-864e5)))"))
    print('ctx sleep', await A.evaluate("coachContext().sommeil_7_nuits.length"), await A.evaluate("JSON.stringify(coachContext().cross.ratio_prevu_dimanche_si_plan_fait)"))
    # projection
    r=await A.evaluate("JSON.stringify((()=>{const W=weekProjection();return {now:W.now&&+W.now.toFixed(2),sun:W.sun&&+W.sun.toFixed(2),tot:Math.round(W.tot),days:W.days.map(o=>[JOURS[dayIdx(o.dt)],Math.round(o.l),o.r&&+o.r.toFixed(2)])};})())")
    print('proj', r)
    print('planLoad', await A.evaluate("JSON.stringify(runPlan(weekIdx()).s.map(s=>[s.k,s.s,Math.round(planLoad(s,getA().P))]))"))
    # cocher la séance du jour fait baisser la charge restante
    t0=await A.evaluate("weekProjection().tot"); await A.evaluate("const k=daySessions(weekIdx(),dayIdx())[0].k;S.done[k]=true;save()"); t1=await A.evaluate("weekProjection().tot")
    print('done reduces', round(t0), '->', round(t1), t1<t0)
    # étoiles
    print('stars', await A.evaluate("JSON.stringify(weekStars(weekIdx()).st.map(s=>[s.n,s.ok,s.x]))"))
    await A.evaluate("for(let i=0;i<5;i++){S.sleep[iso(new Date(sessDate(weekIdx(),0).getTime()+i*864e5))]={h:7.5,q:3,t:9};}save()")
    print('sleep star', await A.evaluate("weekStars(weekIdx()).st[2].ok"))
    print('blocks', await A.evaluate("JSON.stringify(blockBadges())"))
    # dimanche soir : bilan étoiles dans le Coach du jour
    print('cdj dimanche', await A.evaluate("(()=>{const d=new Date(sessDate(weekIdx(),6));d.setHours(21,0,0,0);S.doneAt={};return coachDay(d).p.map(p=>strip(p.t)).join(' | ');})()"))
    # écrans
    await A.evaluate("renderAll();setMod('cross','forme')"); await A.wait_for_timeout(200)
    await A.locator('[data-page=forme] .card:has(h2:has-text("Semaine prévue"))').screenshot(path='l_proj.png')
    await A.locator('[data-page=forme] .card:has(h2:has-text("Sommeil"))').screenshot(path='l_sleep.png')
    await A.evaluate("setMod('cross','cross')"); await A.wait_for_timeout(200)
    await A.locator('[data-page=cross] .card:has(h2:has-text("Étoiles"))').screenshot(path='l_stars.png')
    # utilisateur neuf (sans historique) : rien ne casse
    await A.evaluate("S.activities=[];S.demo=false;S.done={};S.sleep={};S.xact=[];A=null;save();renderAll()")
    print('new user', await A.evaluate("JSON.stringify({p:weekProjection().sun,st:weekStars(Math.max(0,weekIdx())).n})"))
    for t in [['trail','trail'],['muscu','muscu'],['cross','cross'],['cross','forme']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
