"""v8.3 : analyse ultra-précise — allure ajustée (GAP), découplage cardiaque, indice d'efficacité, montées/descentes (VAM), meilleurs efforts, régularité, records & tendances, analyse groupée, fichiers importés."""
import os, math
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
D=os.path.join(APP,'tests','assets')+'/'
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://*.tile.opentopomap.org/**',lambda r:r.abort())
    await A.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
    await A.goto('http://127.0.0.1:8765/index.html'); await A.evaluate("loadDemo();renderAll()")
    # sortie synthétique : 12 km, une côte de 2 km à 8 %, descente, FC qui dérive, 1 km rapide au km 6
    syn="""(()=>{const d=[],t=[],z=[],hr=[];let T=0;for(let i=0;i<=400;i++){const x=i*30;d.push(x);let alt=100;if(x>=2000&&x<4000)alt=100+(x-2000)*.08;else if(x>=4000&&x<5500)alt=260-(x-4000)*.1067;let pace=330;if(x>=2000&&x<4000)pace=470;if(x>=4000&&x<5500)pace=300;if(x>=6000&&x<7000)pace=255;if(i)T+=pace*30/1000;t.push(Math.round(T));z.push(alt);hr.push(Math.round(140+x/12000*14+(x>=2000&&x<4000?12:0)));}return {d,t,alt:z,hr};})()"""
    print('ana', await A.evaluate(f"(()=>{{const a=anaRun({syn});return JSON.stringify({{km:Math.round(a.dist/100)/10,pace:fmtPace(a.pace),gap:fmtPace(a.gap),dec:+(a.dec*100).toFixed(1),ef:+a.ef.toFixed(2),climbs:a.climbs.map(c=>[Math.round(c.at),Math.round(c.dd),c.gain,Math.round(c.g*100),Math.round(c.vam)]),desc:a.descents.map(c=>[Math.round(c.at),c.gain,fmtPace(c.pace)]),best:Object.fromEntries(Object.entries(a.best).map(([k,v])=>[k,fmtDur(v)])),cv:Math.round(a.cv*100)}})}})()"))
    # dans la fiche d'une sortie (démo)
    rid=await A.evaluate("getRuns()[0].id"); await A.evaluate(f"openAct({rid})"); await A.wait_for_timeout(900)
    print('card', await A.evaluate("!!$('#actBody .lum h2')&&$('#actBody').innerText.includes('Analyse avancée')"), 'pc line', await A.evaluate("!!$('#profSvg .pc')"), 'saved', await A.evaluate(f"JSON.stringify(S.eff['{rid}'])"))
    await A.locator('#actBody .card.lum').screenshot(path='a_card.png'); await A.evaluate("closeAct()")
    # analyse groupée + records
    await A.evaluate("showTab('analyse')"); await A.evaluate("anaBatch()"); await A.wait_for_timeout(2500)
    print('eff n', await A.evaluate("Object.keys(S.eff).length"), 'pr 1k', await A.evaluate("JSON.stringify(prOf(1000))"), 'pr 5k', await A.evaluate("!!prOf(5000)"))
    print('records card', await A.evaluate("$('[data-page=analyse]').innerText.includes('Records & tendances')"), 'trend dots', await A.evaluate("document.querySelectorAll('[data-page=analyse] circle[data-tip]').length"))
    await A.locator('[data-page=analyse] .card').first.screenshot(path='a_records.png')
    print('synced', await A.evaluate("'eff' in syncPayload().data"))
    # fichier importé
    ok=await A.evaluate("""(async()=>{const r=await fetch('tests/assets/test_run.gpx');const txt=await r.text();const tr=parseTrack(txt),run=buildRun(tr,'Test GPX');S.imports=[run];save();openImport(run.id);return run.id;})()""")
    await A.wait_for_timeout(300); print('import card', await A.evaluate("$('#sheetBody').innerText.includes('Analyse avancée')"), await A.evaluate(f"!!S.eff['{ok}']"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
