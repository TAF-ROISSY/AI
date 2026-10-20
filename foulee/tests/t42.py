"""v9.0 : saison complète (blocs base / préparation / récup, calage sur la prochaine course A, enchaînement auto, semaines de base, courses B et C dans le plan) et mode ultra (barrières horaires, nuits, conseils)."""
import os, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    await A.evaluate("""(()=>{const D=n=>{const d=new Date();d.setDate(d.getDate()+n);return iso(d)};S.races=[
      {id:'a1',n:'Trail du Printemps',d:D(140),km:32,dp:1500,st:'ins',prio:'A'},
      {id:'b1',n:'10 km de la ville',d:D(5),km:10,dp:50,st:'ins',prio:'B'},
      {id:'c1',n:'Trail nocturne',d:D(20),km:12,dp:300,st:'env',prio:'C'},
      {id:'a2',n:'Ultra des Crêtes',d:D(250),km:80,dp:4200,st:'env',prio:'A'}];save();renderAll();showTab('courses')})()""")
    await A.wait_for_timeout(200)
    print('blocks', await A.evaluate("JSON.stringify(seasonBlocks().map(b=>[b.ty,iso(b.a),iso(b.b),b.r?b.r.n:null]))"))
    print('card', await A.evaluate("$('[data-page=courses]').innerText.includes('Ma saison')"), 'markers', await A.evaluate("document.querySelectorAll('[data-page=courses] .ss-p').length"))
    await A.locator('[data-page=courses] .card:has-text("Ma saison")').screenshot(path='se_card.png')
    # calage
    await A.evaluate("seasonApply()"); print('start', await A.evaluate("S.settings.start"), 'race', await A.evaluate("S.race.name"), 'race week', await A.evaluate("weekIdx(parseISO(S.race.date))"), 'now w', await A.evaluate("weekIdx()"))
    # semaines de base avant le cycle
    print('base', await A.evaluate("S.settings.seasonAuto=true;JSON.stringify([0,1,2,3,4,5,6].flatMap(d=>daySessions(weekIdx(),d)).map(o=>[o.k.slice(0,1),strip(o.t)]))"))
    # course B dans 5 jours et C dans 20 jours sur le plan standard
    await A.evaluate("S.settings.start=iso(mondayOf(new Date()));save()")
    print('B race', await A.evaluate("(()=>{const out=[];for(let i=2;i<=6;i++){const dt=new Date();dt.setDate(dt.getDate()+i);daySessions(weekIdx(dt),dayIdx(dt)).forEach(o=>out.push([i,strip(o.t).slice(0,26),!!o.cancel,!!o.race]));}return JSON.stringify(out)})()"))
    print('C race', await A.evaluate("(()=>{const dt=new Date();dt.setDate(dt.getDate()+20);return JSON.stringify(daySessions(weekIdx(dt),dayIdx(dt)).map(o=>[strip(o.t).slice(0,30),!!o.race]))})()"))
    # enchaînement auto : course A passée il y a 10 jours
    await A.evaluate("(()=>{const d=new Date();d.setDate(d.getDate()-10);S.races.push({id:'a0',n:'Trail passé',d:iso(d),km:20,prio:'A',st:'fait'});S.settings.start='2026-01-05';S.race={name:'Trail passé',date:iso(d),km:20};save();seasonTick()})()")
    print('auto', await A.evaluate("S.race.name+' · '+S.settings.start"))
    # mode ultra
    await A.evaluate("(()=>{const d=new Date();d.setDate(d.getDate()+4);S.race={name:'Ultra des Crêtes',date:iso(d),km:80,dp:4200,aid:[20,40,60],cuts:'40 = 22h00\\n60 = J+1 03h30',gpx:null};save();})()")
    print('ultra', await A.evaluate("isUltra()"), 'cuts', await A.evaluate("JSON.stringify(cutParse(S.race.cuts))"))
    print('sun', await A.evaluate("(()=>{const s=sunTimes(new Date(2026,5,21),45.9,6.87);return s.rise.toTimeString().slice(0,5)+' '+s.set.toTimeString().slice(0,5)})()"))
    await A.evaluate("openRaceDay()"); await A.wait_for_timeout(150)
    print('sheet', await A.evaluate("$('#sheetBody').innerText.toLowerCase().includes('mode ultra')"), 'cut rows', await A.evaluate("document.querySelectorAll('#sheetBody .tbl')[1]?document.querySelectorAll('#sheetBody .tbl')[1].rows.length:0"), 'night', await A.evaluate("$('#sheetBody').innerText.includes('Nuit')"))
    await A.screenshot(path='u_sheet.png',full_page=True)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
