"""v6.8 : onglet Courses du module Trail — planning des courses, calendrier des trails de l'Oise (filtres, tri, carte), recherche en ligne par le coach."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets'); D=AS+'/'
import asyncio, json, subprocess, time, io
from playwright.async_api import async_playwright
from PIL import Image
im=Image.new('RGB',(256,256),(210,214,200)); b=io.BytesIO(); im.save(b,'PNG'); TILE=b.getvalue()
WEB={"courses":[{"nom":"Trail de la Baie","commune":"Saint-Valery-sur-Somme","date":"2027-04-11","distances_km":[12,25,1],"dplus_m":250,"url":"https://exemple.fr/baie"},{"nom":"Sans date","commune":"X","date":"bientôt","distances_km":[10]}]}
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':49.2156,'longitude':2.5912},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x))); calls=[]
    n={'i':0}
    async def ant(r):
        bd=json.loads(r.request.post_data); calls.append(bd); n['i']+=1
        if n['i']==1:  # première réponse : recherche longue mise en pause
            body={'content':[{'type':'server_tool_use','id':'srv1','name':'web_search','input':{'query':'trail Somme 2027'}}],'stop_reason':'pause_turn'}
        else:
            body={'content':[{'type':'text','text':'Voici : '+json.dumps(WEB)}],'stop_reason':'end_turn'}
        await r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(body))
    await A.route('https://api.anthropic.com/**',ant)
    await A.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
    await A.route('https://*.tile.opentopomap.org/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.races=[];S.race=null;save();renderAll();setMod('trail','courses')"); await A.wait_for_timeout(300)
    print('tabs', await A.evaluate("[...document.querySelectorAll('#tabs button')].map(b=>b.textContent.trim())"))
    print('list all', await A.evaluate("CS.per='all';oiseList().length"), 'geo ok', await A.evaluate("OISE_TRAILS.every(t=>OISE_GEO[t[2]])"))
    print('6 mois', await A.evaluate("CS.per='6m';oiseList().length"), 'first', await A.evaluate("oiseList()[0].n+' · '+oiseList()[0].d"))
    print('no past', await A.evaluate("oiseList().every(o=>rWhen(o.d)>=new Date(new Date().getFullYear(),new Date().getMonth(),1))"))
    print('22-36', await A.evaluate("CS.per='all';CS.dist='l';oiseList().map(o=>o.n).slice(0,4)"))
    print('search senlis', await A.evaluate("CS.dist='all';CS.q='senlis';oiseList().map(o=>o.n)"), 'accents', await A.evaluate("CS.q='compiegne';oiseList().length"))
    await A.evaluate("CS.q='';CS.per='6m';renderCourses()")
    # près de moi (Senlis)
    await A.evaluate("csNear()"); await A.wait_for_timeout(400)
    print('near', await A.evaluate("oiseList().slice(0,3).map(o=>o.n+' '+Math.round(o.km)+' km')"))
    # ajouter deux courses proches + une longue
    await A.evaluate("addFound('senlis',29);addFound('pontoise',25);addFound('orry',21)"); await A.wait_for_timeout(100)
    print('races', await A.evaluate("JSON.stringify(S.races.map(r=>[r.n,r.d,r.km,r.st,r.prio]))"))
    print('obj', await A.evaluate("JSON.stringify(S.race&&{n:S.race.name,d:S.race.date,km:S.race.km})"), 'taper', await A.evaluate("JSON.stringify(taperFor(new Date(parseISO(S.race.date)-2*864e5)))"))
    txt=await A.evaluate("document.querySelector('[data-page=courses]').innerText")
    print('warn', 'Calendrier chargé' in txt, '| J-', 'J-' in txt)
    await A.screenshot(path='m_courses.png',full_page=False)
    await A.evaluate("window.scrollTo(0,0)")
    # statut et priorité
    rid=await A.evaluate("S.races.find(r=>r.src==='orry').id")
    await A.evaluate(f"raceCycle('{rid}')"); print('cycle', await A.evaluate(f"S.races.find(r=>r.id==='{rid}').st"))
    await A.evaluate(f"racePrio('{rid}')"); print('prio', await A.evaluate(f"S.races.find(r=>r.id==='{rid}').prio"), 'obj now', await A.evaluate("S.race.name"))
    # même distance = retrait (confirm)
    A.once('dialog',lambda d: asyncio.ensure_future(d.accept()))
    await A.evaluate("addFound('pontoise',25)"); await A.wait_for_timeout(100); print('removed', await A.evaluate("!S.races.some(r=>r.src==='pontoise')"), await A.evaluate("S.del.races.length"))
    # course à la main avec résultat
    await A.evaluate("openRaceEdit()"); await A.wait_for_timeout(100)
    await A.fill('#re_n','Trail des Lacs'); await A.fill('#re_v','Annecy'); await A.fill('#re_d','2026-09-20'); await A.fill('#re_km','30'); await A.fill('#re_dp','1200'); await A.fill('#re_res','3:42')
    await A.evaluate("reSync();RED.st='fait';renderRaceEdit()"); await A.screenshot(path='m_edit.png')
    await A.evaluate("saveRaceEdit()"); await A.wait_for_timeout(100)
    print('manual', await A.evaluate("JSON.stringify(S.races.filter(r=>r.n==='Trail des Lacs').map(r=>[r.d,r.km,r.dp,r.st,r.res]))"))
    # mois à confirmer ne devient pas objectif
    await A.evaluate("addFound('pierrefonds',27)"); p=await A.evaluate("S.races.find(r=>r.src==='pierrefonds').id")
    await A.evaluate(f"S.races.find(r=>r.id==='{p}').prio='C';racePrio('{p}');racePrio('{p}');racePrio('{p}')")
    print('month tbc A', await A.evaluate(f"S.races.find(r=>r.id==='{p}').prio"), 'obj kept', await A.evaluate("S.race.name"))
    # contexte du coach
    print('ctx', await A.evaluate("JSON.stringify(coachContext().courses_prevues.map(c=>c.nom+' '+c.priorite))"), await A.evaluate("coachContext().courses_faites.length"))
    # carte
    await A.evaluate("CS.map=true;renderCourses()"); await A.wait_for_timeout(900)
    print('map markers', await A.evaluate("document.querySelectorAll('#csMap path.leaflet-interactive').length"))
    await A.locator('[data-page=courses] .card:has(h2:has-text("Trouver"))').screenshot(path='m_find.png')
    # recherche en ligne (pause_turn puis JSON)
    await A.evaluate("localStorage.setItem('foulee_api','sk-test');CS.map=false;renderCourses()")
    await A.fill('#cs_zone','Somme (80)'); await A.evaluate("raceWebSearch()"); await A.wait_for_timeout(800)
    print('web calls', len(calls), 'tool', calls[0]['tools'][0]['type'], calls[0]['tools'][0].get('max_uses'), 'resent paused', calls[-1]['messages'][-1]['role'] if len(calls)>1 else None)
    print('web items', await A.evaluate("JSON.stringify(CS.web.items.map(o=>[o.n,o.d,o.ds,o.src]))"), 'in list', await A.evaluate("CS.per='all';oiseList().some(o=>o.n==='Trail de la Baie')"))
    print('persist', await A.evaluate("S.raceWeb.zone"), 'nosync', await A.evaluate("!('raceWeb' in syncPayload().data)"))
    await A.evaluate("addFound(CS.web.items[0].id,25)"); print('web add', await A.evaluate("JSON.stringify(S.races.filter(r=>r.n==='Trail de la Baie').map(r=>[r.km,r.url]))"))
    for t in [['trail','trail'],['trail','plan'],['trail','courses'],['cross','forme']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
