"""v6.9 : Adeorun comme source ; tracé GPX trouvé automatiquement pour une course du planning (web_search + web_fetch), repli lien + import manuel."""
import os, math
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
def gpx(km,name='Trail de Senlis 29 km',cut=False):
    n=int(km*1000/20); pts=[]
    lat,lon=49.2156,2.5912
    for i in range(n+1):
        d=i*20; h=d/3000
        pts.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{60+40*math.sin(d/1500):.1f}</ele></trkpt>')
        lat+=20*math.cos(h)/111320; lon+=20*math.sin(h)/(111320*math.cos(math.radians(lat)))
    s=f'<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><name>{name}</name><trkseg>'+''.join(pts)+'</trkseg></trk></gpx>'
    return s[:len(s)*2//3] if cut else s
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'out'); os.makedirs(OUT,exist_ok=True)
open(os.path.join(OUT,'senlis15.gpx'),'w').write(gpx(15.2,'Senlis 15 km'))
MODE={'m':'fetch'}
def reply(bd):
    m=MODE['m']; js=lambda o:{'type':'text','text':json.dumps(o)}
    if m=='fetch':
        return {'content':[{'type':'server_tool_use','id':'s1','name':'web_search','input':{'query':'trail de senlis 29 km gpx'}},
          {'type':'server_tool_use','id':'s2','name':'web_fetch','input':{'url':'https://exemple.fr/senlis29.gpx'}},
          {'type':'web_fetch_tool_result','tool_use_id':'s2','content':{'type':'web_fetch_result','url':'https://exemple.fr/senlis29.gpx','content':{'type':'document','source':{'type':'text','media_type':'text/plain','data':gpx(29.3)},'title':'senlis29.gpx'}}},
          js({'gpx_url':'https://exemple.fr/senlis29.gpx','page_url':'https://trail-de-senlis.adeorun.com','source':'Adeorun','km':29,'dplus_m':420,'remarque':'Tracé officiel 2026.'})],'stop_reason':'end_turn'}
    if m=='links':
        return {'content':[js({'gpx_url':None,'page_url':'https://connect.garmin.com/modern/course/58038319','source':'Garmin Connect','km':15,'dplus_m':180,'remarque':'Tracé sur Garmin Connect, compte nécessaire pour télécharger.'})],'stop_reason':'end_turn'}
    if m=='direct':
        return {'content':[js({'gpx_url':'https://cors-ok.exemple.fr/orry21.gpx','page_url':None,'source':'Openrunner','km':21,'dplus_m':200,'remarque':'ok'})],'stop_reason':'end_turn'}
    if m=='cut':
        return {'content':[{'type':'web_fetch_tool_result','tool_use_id':'s2','content':{'type':'web_fetch_result','url':'https://exemple.fr/coupe.gpx','content':{'type':'document','source':{'type':'text','media_type':'text/plain','data':gpx(25,cut=True)}}}},js({'gpx_url':'https://exemple.fr/coupe.gpx','page_url':None,'source':'x','km':25,'dplus_m':None,'remarque':''})],'stop_reason':'end_turn'}
    if m=='wrong':
        return {'content':[{'type':'web_fetch_tool_result','tool_use_id':'s2','content':{'type':'web_fetch_result','url':'https://exemple.fr/autre.gpx','content':{'type':'document','source':{'type':'text','media_type':'text/plain','data':gpx(12)}}}},js({'gpx_url':'https://exemple.fr/autre.gpx','page_url':None,'source':'x','km':12,'dplus_m':None,'remarque':''})],'stop_reason':'end_turn'}
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x))); calls=[]
    async def ant(r):
        bd=json.loads(r.request.post_data); calls.append(bd)
        await r.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(reply(bd)))
    await A.route('https://api.anthropic.com/**',ant)
    await A.route('https://cors-ok.exemple.fr/**',lambda r: r.fulfill(status=200,content_type='application/gpx+xml',headers={'access-control-allow-origin':'*'},body=gpx(21.4,'Orry 21')))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.races=[];S.race=null;save();renderAll();setMod('trail','courses')"); await A.wait_for_timeout(300)
    # Adeorun
    print('adeorun links', await A.evaluate("OISE_TRAILS.filter(t=>t[6]&&t[6].includes('adeorun')).length"), 'pierrefonds', await A.evaluate("OISE_TRAILS.find(t=>t[0]==='pierrefonds')[3]"), 'blacourt', await A.evaluate("OISE_TRAILS.find(t=>t[0]==='blacourt')[3]"))
    print('link senlis', await A.evaluate("CS.per='all';oiseList().find(o=>o.id==='senlis').url"), 'source note', await A.evaluate("document.querySelector('[data-page=courses]').innerText.includes('Sources : Adeorun')"))
    # sans clé : pas de recherche auto, chip
    await A.evaluate("addFound('senlis',29)"); await A.wait_for_timeout(1500)
    print('no key calls', len(calls), 'chip', await A.evaluate("document.querySelector('[data-page=courses]').innerText.includes('Trouver le GPX')"))
    # avec clé : recherche manuelle, GPX récupéré par web_fetch
    await A.evaluate("localStorage.setItem('foulee_api','sk-test');renderAll()")
    sid=await A.evaluate("S.races[0].id")
    await A.evaluate(f"findGpx('{sid}')"); await A.wait_for_timeout(800)
    bd=calls[-1]; print('tools', [t['type'] for t in bd['tools']], 'url in msg', 'adeorun.com' in bd['messages'][0]['content'], '29 km' in bd['messages'][0]['content'])
    print('attached', await A.evaluate(f"JSON.stringify(S.races.find(r=>r.id==='{sid}').gpxInfo)"), 'pts', await A.evaluate(f"S.races.find(r=>r.id==='{sid}').gpx.pts.length"))
    print('obj gpx', await A.evaluate("!!(S.race&&S.race.gpx)"), 'strategy km', await A.evaluate("Math.round(raceStrategy(S.race).segs?raceStrategy(S.race).segs.length:0)>=0"), await A.evaluate("JSON.stringify(Object.keys(raceStrategy(S.race)).slice(0,6))"))
    print('chip ok', await A.evaluate("document.querySelector('[data-page=courses]').innerText.match(/🗺️ [^\\n]*D\\+/)?.[0]"))
    # auto à l'ajout (liens seulement)
    MODE['m']='links'; n0=len(calls)
    await A.evaluate("addFound('senlis',15)"); await A.wait_for_timeout(2200)
    print('auto on distance change', len(calls)-n0, await A.evaluate(f"JSON.stringify(S.races.find(r=>r.id==='{sid}').gpxLinks)"), 'gpx cleared', await A.evaluate(f"!S.races.find(r=>r.id==='{sid}').gpx"))
    print('obj follows', await A.evaluate("JSON.stringify({km:S.race.km,gpx:!!S.race.gpx})"))
    print('dp from coach', await A.evaluate(f"S.races.find(r=>r.id==='{sid}').dp"))
    # import manuel dans la fiche
    await A.evaluate(f"openRaceEdit('{sid}')"); await A.wait_for_timeout(100)
    await A.screenshot(path='n_edit_links.png')
    await A.set_input_files('#sheetBody input[type=file]',os.path.join(OUT,'senlis15.gpx')); await A.wait_for_timeout(400)
    print('imported draft', await A.evaluate("JSON.stringify(RED.gpxInfo)"))
    await A.evaluate("saveRaceEdit()"); await A.wait_for_timeout(200); print('saved import', await A.evaluate(f"S.races.find(r=>r.id==='{sid}').gpxInfo.src"))
    await A.evaluate(f"openRaceEdit('{sid}')"); await A.wait_for_timeout(100); await A.screenshot(path='n_edit_gpx.png'); await A.evaluate("closeSettings()")
    # lien direct récupérable par le navigateur (CORS ouvert)
    MODE['m']='direct'; await A.evaluate("addFound('orry',21)"); await A.wait_for_timeout(2200)
    print('direct', await A.evaluate("JSON.stringify(S.races.find(r=>r.src==='orry').gpxInfo)"))
    # fichier coupé, mauvaise distance
    MODE['m']='cut'; await A.evaluate("addFound('pontoise',25)"); await A.wait_for_timeout(2200)
    print('cut', await A.evaluate("JSON.stringify(S.races.find(r=>r.src==='pontoise').gpxInfo)"))
    MODE['m']='wrong'; await A.evaluate("addFound('noctrail',24)"); await A.wait_for_timeout(2200)
    print('wrong', await A.evaluate("JSON.stringify(S.races.find(r=>r.src==='noctrail').gpxInfo)"))
    # saisie manuelle du format dans une course ajoutée à la main → recherche auto
    MODE['m']='fetch'; n0=len(calls)
    await A.evaluate("openRaceEdit()"); await A.fill('#re_n','Trail de Senlis bis'); await A.fill('#re_d','2026-11-29'); await A.evaluate("saveRaceEdit()"); await A.wait_for_timeout(800)
    print('no km no search', len(calls)-n0)
    rid=await A.evaluate("S.races.find(r=>r.n==='Trail de Senlis bis').id")
    await A.evaluate(f"openRaceEdit('{rid}')"); await A.fill('#re_km','29'); await A.evaluate("saveRaceEdit()"); await A.wait_for_timeout(1500)
    print('km set → search', len(calls)-n0, await A.evaluate(f"!!S.races.find(r=>r.id==='{rid}').gpx"))
    # réglage coupé
    await A.evaluate("S.settings.gpxAuto=false;save()"); n0=len(calls); await A.evaluate("addFound('gury',12)"); await A.wait_for_timeout(1600); print('auto off', len(calls)-n0)
    await A.evaluate("openSettings()"); print('setting box', await A.evaluate("document.querySelector('#s_gpx').checked")); await A.evaluate("closeSettings()")
    await A.evaluate("renderAll()"); await A.wait_for_timeout(200)
    await A.locator('[data-page=courses] .card:has(h2:has-text("Mon planning"))').screenshot(path='n_planning.png')
    print('sync size kb', await A.evaluate("Math.round(JSON.stringify(syncPayload().data.races).length/1024)"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
