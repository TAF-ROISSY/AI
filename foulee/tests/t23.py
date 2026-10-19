"""v7.0 : calendrier des épreuves — périmètre (Oise, Hauts-de-France, Île-de-France), distance, D+, type, période ; Autour de moi (rayon, tri secondaire) ; événements terminés ; fiche épreuve (profil, liens, objectif) ; météo prévisionnelle ; cache IndexedDB."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets'); D=AS+'/'
import asyncio, json, subprocess, time, io
from playwright.async_api import async_playwright
from PIL import Image
im=Image.new('RGB',(256,256),(210,214,200)); b=io.BytesIO(); im.save(b,'PNG'); TILE=b.getvalue()
def meteo(r):
    from urllib.parse import urlparse, parse_qs
    q=parse_qs(urlparse(r.request.url).query); d=q['start_date'][0]
    H={'time':[f'{d}T{h:02d}:00' for h in range(24)],'temperature_2m':[14+h*.6 for h in range(24)],'relative_humidity_2m':[70]*24,'dew_point_2m':[17]*24,'wind_speed_10m':[32]*24,'precipitation_probability':[40]*24}
    return r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'hourly':H}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':49.4006,'longitude':2.8547},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x))); wx=[]
    await A.route('https://api.open-meteo.com/**',lambda r:(wx.append(r.request.url),meteo(r))[1])
    await A.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
    await A.route('https://*.tile.opentopomap.org/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.races=[];S.race=null;save();renderAll();setMod('trail','courses')"); await A.wait_for_timeout(300)
    print('version', await A.evaluate("APP_VER"))
    # ordre chronologique par défaut, périmètre Oise
    print('default', await A.evaluate("JSON.stringify({reg:CS.reg,sort:CS.sort,per:CS.per})"), 'chrono', await A.evaluate("(()=>{const L=oiseList();return L.every((o,i)=>!i||rWhen(L[i-1].d)<=rWhen(o.d));})()"))
    for reg in ['oise','hdf','idf','all']:
        print('reg',reg, await A.evaluate(f"CS.reg='{reg}';CS.per='all';oiseList().length"), await A.evaluate("JSON.stringify([...new Set(oiseList().map(o=>o.dep))].sort())"))
    await A.evaluate("CS.reg='all'")
    for t in ['nuit','urban','obst']:
        print('type',t, await A.evaluate(f"CS.type='{t}';oiseList().map(o=>o.n).slice(0,4).join(' | ')"))
    await A.evaluate("CS.type='all'")
    for dpb in ['lo','mid','hi']:
        print('dp',dpb, await A.evaluate(f"CS.dp='{dpb}';oiseList().map(o=>o.n+' '+o.dpMax).join(' | ')"))
    await A.evaluate("CS.dp='all'")
    print('dist >35', await A.evaluate("CS.dist='d';oiseList().map(o=>o.n).slice(0,5).join(' | ')"), '| <10', await A.evaluate("CS.dist='a';oiseList().length"))
    await A.evaluate("CS.dist='all'")
    print('30 jours', await A.evaluate("CS.per='30j';oiseList().every(o=>(rWhen(o.d)-new Date())/864e5<=30)"), await A.evaluate("oiseList().length"))
    # Autour de moi (Compiègne), rayon, tri secondaire
    await A.evaluate("CS.reg='oise';CS.per='all';renderCourses();csNear()"); await A.wait_for_timeout(400)
    print('near on', await A.evaluate("JSON.stringify({me:!!CS.me,rad:RADII[CS.rad],sort:CS.sort})"), 'all within', await A.evaluate("oiseList().every(o=>o.km<=30)"), 'chrono kept', await A.evaluate("(()=>{const L=oiseList();return L.every((o,i)=>!i||rWhen(L[i-1].d)<=rWhen(o.d));})()"))
    for r in [1,2,3,4]:
        print('rad',r, await A.evaluate(f"CS.rad={r};oiseList().length"))
    await A.evaluate("CS.rad=2;CS.per='30j';CS.sort='near'")
    print('proches 30 j', await A.evaluate("oiseList().map(o=>o.n+' '+Math.round(o.km)+' km').join(' | ')"))
    await A.evaluate("CS.sort='date';CS.per='6m';CS.rad=3;CS.map=true;renderCourses()"); await A.wait_for_timeout(900)
    print('pins', await A.evaluate("document.querySelectorAll('#csMap .ev-pin').length"), 'radius circle', await A.evaluate("document.querySelectorAll('#csMap path.leaflet-interactive').length>=1"))
    await A.locator('[data-page=courses] .card:has(h2:has-text("Calendrier des trails"))').screenshot(path='o_calendar.png')
    # événements terminés
    await A.evaluate("CS.map=false;CS.web=[{k:'web:test',zone:'test',at:Date.now(),items:[{id:'wpast',n:'Trail passé',v:'Senlis',dep:'60',d:iso(new Date(Date.now()-20*864e5)),ds:[15],t:'jour',dpk:{},src:'web'}]}];CS.me=null;renderCourses()")
    print('past block', await A.evaluate("oiseList({past:true}).map(o=>o.n)"), await A.evaluate("document.querySelector('[data-page=courses]').innerText.includes('Événements terminés (1)')"), 'not in main', await A.evaluate("!oiseList().some(o=>o.id==='wpast')"))
    # fiche épreuve avec météo (Tour du Grand Parc : J-6)
    await A.evaluate("openEvent('grandparc')"); await A.wait_for_timeout(600)
    t=await A.evaluate("$('#sheetBody').innerText")
    print('fiche', 'D+ non publié' in t, 'Météo prévue' in t, 'Allures ralenties' in t, 'Vent fort' in t, 'Définir comme objectif' in t, 'wx calls', len(wx), 'url ok', 'latitude=49.401' in wx[-1] and 'start_date=2026-10-25' in wx[-1])
    await A.locator('#sheetBody').screenshot(path='o_fiche.png')
    await A.evaluate("evSetGoal()"); await A.wait_for_timeout(200)
    print('goal', await A.evaluate("JSON.stringify({n:S.race.name,km:S.race.km,temp:S.race.temp,hum:S.race.hum})"), 'planning A', await A.evaluate("S.races.find(r=>r.src==='grandparc').prio"))
    print('strategy heat', await A.evaluate("raceStrategy(S.race).T>0"))
    # fiche d'une course lointaine, liens Adeorun
    await A.evaluate("openEvent('senlis')"); await A.wait_for_timeout(200); t=await A.evaluate("$('#sheetBody').innerText")
    print('far', 'J-14' in t, 'S’inscrire' in t, await A.evaluate("[...document.querySelectorAll('#sheetBody a')].map(a=>a.href).join(' ')"))
    await A.evaluate("EVD.km=15;renderEvent()"); print('switch km', await A.evaluate("$('#sheetBody').innerText.includes('Définir comme objectif (15 km)')"))
    await A.evaluate("openEvent('beaumont')"); await A.wait_for_timeout(100); await A.locator('#sheetBody').screenshot(path='o_fiche_dp.png'); print('dp profile', await A.evaluate("$('#sheetBody').innerText.match(/Profil simplifié[^.]*/)?.[0]"))
    await A.evaluate("openEvent('clermontrail')"); await A.wait_for_timeout(100); print('tbc goal disabled', await A.evaluate("[...document.querySelectorAll('#sheetBody button')].find(b=>b.textContent.includes('Définir')).disabled"))
    await A.evaluate("closeSettings()")
    # cache IndexedDB : migration de l'ancien S.raceWeb puis rechargement
    await A.evaluate("S.raceWeb={zone:'Somme (80)',at:Date.now(),items:[{id:'wbaie',n:'Trail de la Baie',v:'Saint-Valery-sur-Somme',dep:'80',d:'2027-04-11',ds:[12,25],dpk:{},t:'jour',src:'web'}]};save(true)")
    await A.reload(); await A.wait_for_timeout(1200)
    print('migrated', await A.evaluate("JSON.stringify({web:CS.web.map(w=>w.zone),old:!!S.raceWeb})"), await A.evaluate("EVDB.all().then(a=>a.length)"))
    print('idb stores', await A.evaluate("IDB.open().then(db=>[...db.objectStoreNames].join(','))"), 'version', await A.evaluate("IDB.open().then(db=>db.version)"))
    print('found after reload', await A.evaluate("CS.reg='all';CS.per='all';oiseList().some(o=>o.n==='Trail de la Baie')"))
    for t in [['trail','trail'],['trail','courses'],['muscu','suivi'],['cross','forme']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
