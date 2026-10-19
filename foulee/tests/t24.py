"""v7.1 : partage des courses du planning vers le calendrier famille (.ics iPhone, Google Agenda, envoi), état partagé / à mettre à jour.
Le fichier .ics est validé avec la bibliothèque icalendar (pip install icalendar)."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from urllib.parse import unquote
from playwright.async_api import async_playwright
try:
    import icalendar
except ImportError:
    icalendar=None
IOS='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
def check(ics,label):
    if not icalendar: print(label,'(icalendar absent)'); return
    cal=icalendar.Calendar.from_ical(ics); evs=[c for c in cal.walk('VEVENT')]
    out=[]
    for e in evs:
        al=[a for a in e.walk('VALARM')]
        out.append({'s':str(e.get('SUMMARY')),'start':e.decoded('DTSTART').isoformat(),'tz':str(getattr(e.decoded('DTSTART'),'tzinfo',None)),'end':e.decoded('DTEND').isoformat(),'loc':str(e.get('LOCATION')),'uid':str(e.get('UID')),'seq':int(e.get('SEQUENCE')),'alarm':str(al[0].get('TRIGGER').to_ical().decode()) if al else None,'status':str(e.get('STATUS')) if e.get('STATUS') else None})
    print(label, json.dumps(out,ensure_ascii=False))
    print(label,'lines<=75 octets', all(len(l.encode())<=75 for l in ics.split('\r\n')), 'crlf', '\r\n' in ics and '\n' not in ics.replace('\r\n',''))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script("window.__open=[];window.open=(u)=>{window.__open.push(u);return {};};window.__shared=[];navigator.canShare=()=>true;navigator.share=async(d)=>{window.__shared.push({n:d.files?d.files.map(f=>f.name):[],t:d.text});};")
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.races=[];S.race=null;S.settings.gpxAuto=false;save();renderAll();setMod('trail','courses')"); await A.wait_for_timeout(300)
    await A.evaluate("addFound('senlis',29);addFound('pontoise',25);addFound('clermontrail',16)"); await A.wait_for_timeout(200)
    print('chips', await A.evaluate("document.querySelector('[data-page=courses]').innerText.split('📅 Famille').length-1"), 'tbc no chip', await A.evaluate("calChip(S.races.find(r=>r.src==='clermontrail'))===''"))
    sid=await A.evaluate("S.races.find(r=>r.src==='senlis').id")
    print('start 29 km', await A.evaluate(f"raceStart(S.races.find(r=>r.id==='{sid}')).toTimeString().slice(0,5)"), '15 km', await A.evaluate(f"(()=>{{const r={{...S.races.find(x=>x.id==='{sid}'),km:15}};return raceStart(r).toTimeString().slice(0,5);}})()"))
    # partage d'une course (navigateur de bureau : téléchargement)
    await A.evaluate("S.settings.calWho='Christophe';save()")
    await A.evaluate(f"openCalShare('{sid}')"); await A.wait_for_timeout(100); await A.locator('#sheetBody').screenshot(path='p_share.png')
    async with A.expect_download() as dl: await A.evaluate("calIcs()")
    d=await dl.value; print('download', d.suggested_filename)
    ics=await A.evaluate("window.__lastIcs"); check(ics,'senlis')
    print('state', await A.evaluate(f"calState(S.races.find(r=>r.id==='{sid}'))"))
    # changement de date → à mettre à jour, séquence +1
    await A.evaluate(f"S.races.find(r=>r.id==='{sid}').d='2026-11-28';save();renderCourses()")
    print('after change', await A.evaluate(f"calState(S.races.find(r=>r.id==='{sid}'))"), await A.evaluate("document.querySelector('[data-page=courses]').innerText.includes('Famille · à mettre à jour')"))
    await A.evaluate(f"openCalShare('{sid}')"); print('warn shown', await A.evaluate("$('#sheetBody').innerText.includes('a changé')"))
    async with A.expect_download(): await A.evaluate("calIcs()")
    check(await A.evaluate("window.__lastIcs"),'senlis v2')
    # course journée entière (heure inconnue)
    pid=await A.evaluate("S.races.find(r=>r.src==='pontoise').id")
    await A.evaluate(f"openCalShare('{pid}')"); gurl=await A.evaluate("[...document.querySelectorAll('#sheetBody a')].find(a=>a.href.includes('calendar.google'))?.href")
    print('google', unquote(gurl)[:160])
    await A.evaluate("CALD=CALD;"); t=await A.evaluate("icsFor(calList())"); check(t,'pontoise')
    # envoi (share sheet avec fichier)
    await A.evaluate("calSend()"); await A.wait_for_timeout(200); print('shared', await A.evaluate("JSON.stringify(window.__shared)"))
    # tout le planning
    await A.evaluate("openCalShare('*')"); await A.wait_for_timeout(100); print('all ids', await A.evaluate("CALD.ids.length"))
    async with A.expect_download() as dl: await A.evaluate("calIcs()")
    d=await dl.value; print('download all', d.suggested_filename); check(await A.evaluate("window.__lastIcs"),'all')
    # date à confirmer refusée
    cid=await A.evaluate("S.races.find(r=>r.src==='clermontrail').id"); await A.evaluate(f"closeSettings();openCalShare('{cid}')")
    print('tbc refused', await A.evaluate("!$('#sheet').classList.contains('on')||!$('#sheetBody').innerText.includes('Ajouter au calendrier')"))
    # passage en Inscrit → la feuille s'ouvre
    await A.evaluate("closeSettings()"); nid=await A.evaluate("addFound('noctrail',16);S.races.find(r=>r.src==='noctrail').id")
    await A.evaluate(f"raceCycle('{nid}')"); await A.wait_for_timeout(100); print('inscrit opens', await A.evaluate("$('#sheet').classList.contains('on')&&$('#sheetBody').innerText.includes('Calendrier famille')"))
    await A.evaluate("closeSettings()")
    print('sync keeps cal', await A.evaluate("!!syncPayload().data.races.find(r=>r.cal)"))
    await A.evaluate("renderCourses()"); await A.wait_for_timeout(100)
    await A.locator('[data-page=courses] .card:has(h2:has-text("Mon planning"))').screenshot(path='p_planning.png')
    print('ERR',errs); await ctx.close()
    # iPhone : ouverture du .ics dans le calendrier
    ctx2=await br.new_context(viewport={'width':390,'height':844},user_agent=IOS); B=await ctx2.new_page(); errs2=[]; B.on('pageerror',lambda x:errs2.append(str(x)))
    await B.add_init_script("window.__open=[];window.open=(u)=>{window.__open.push(u);return {};};")
    await B.route('https://fonts.**',lambda r:r.abort()); await B.goto('http://127.0.0.1:8765/index.html')
    await B.evaluate("loadDemo();S.races=[];S.settings.gpxAuto=false;save();addFound('senlis',29);openCalShare(S.races[0].id);calIcs()"); await B.wait_for_timeout(200)
    u=await B.evaluate("window.__open[0]||''"); print('ios data url', u[:40], 'BEGIN:VCALENDAR' in unquote(u))
    print('ERR ios',errs2); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
