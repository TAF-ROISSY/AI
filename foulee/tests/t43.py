"""v9.1 : prédicteur & indice de performance (Riegel, trail par tronçons, courbe mensuelle), mes côtes (détection des montées répétées dans les sorties en cache, historique, record, nom), carnet imprimable."""
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
    await A.evaluate("loadDemo();renderAll();showTab('analyse')"); await A.wait_for_timeout(300)
    print('pred', await A.evaluate("JSON.stringify({pi:perfIndex(getA().P.t10),t10:fmtDur(getA().P.t10),trail:fmtH(predTrail(25,1000)),flat:fmtH(predTrail(25,0))})"))
    print('card', await A.evaluate("$('[data-page=analyse]').innerText.includes('Prédictions & indice')"), 'months', await A.evaluate("Object.keys(monthBest()).length"))
    await A.fill('#pd_km','42'); await A.fill('#pd_dp','2000'); await A.locator('[data-page=analyse] button:has-text("Prédire")').click(); await A.wait_for_timeout(150)
    print('custom', await A.evaluate("$('[data-page=analyse]').innerText.match(/42 km · 2000 m D\\+ : [^ ]+/)[0]"))
    await A.locator('[data-page=analyse] .card:has-text("Prédictions")').screenshot(path='p_pred.png')
    # côtes : ouvrir 3 sorties démo (même boucle → mêmes montées)
    ids=await A.evaluate("getRuns().slice(0,3).map(r=>r.id)")
    for n,i in enumerate(ids):
        await A.evaluate(f"""(()=>{{const d=[],t=[],alt=[],ll=[],hr=[];let T=0;for(let k=0;k<=240;k++){{const x=k*25;d.push(x);let z=100;if(x>=1500&&x<2700)z=100+(x-1500)*.09;else if(x>=2700)z=208;const pace=(x>=1500&&x<2700)?{430+n*25}:330;if(k)T+=pace*25/1000;t.push(Math.round(T));alt.push(z);ll.push([45.9+x/111320,6.1]);hr.push(150);}}cachePut({i},{{d,t,alt,ll,hr}});}})()""")
    print('climbs ia', await A.evaluate(f"(()=>{{const a=anaRun(cacheGet({ids[0]}));return a&&a.climbs[0]?[a.climbs[0].ia!=null,a.climbs[0].ib!=null]:'none'}})()"))
    H=await A.evaluate("JSON.stringify(hillsScan().map(h=>[hillName(h),h.ef.length,fmtDur(h.best.t)]))"); print('hills', H)
    await A.evaluate("renderAnalyse()"); print('hills card', await A.evaluate("$('[data-page=analyse]').innerText.includes('Mes côtes')"))
    if await A.evaluate("hillsScan().length"):
        await A.evaluate("openHill(0)"); await A.fill('#hl_n','Côte du lavoir'); await A.locator('#hl_n').dispatch_event('change'); await A.wait_for_timeout(100)
        print('renamed', await A.evaluate("hillName(hillsScan()[0])"), 'synced', await A.evaluate("'hillNames' in syncPayload().data")); await A.screenshot(path='h_sheet.png'); await A.evaluate("closeSettings()")
    # carnet imprimable
    await A.evaluate("window.print=()=>{window.__pp=1}")
    await A.evaluate("printBook()"); print('print', await A.evaluate("window.__pp"), await A.evaluate("$('#printArea').innerText.includes('Plan des 4 prochaines semaines')"), 'rows', await A.evaluate("$('#printArea').querySelectorAll('tr').length"))
    await A.emulate_media(media='print'); await A.wait_for_timeout(100)
    print('print css', await A.evaluate("getComputedStyle($('main')).display"), await A.evaluate("getComputedStyle($('#printArea')).display"))
    await A.pdf(path='carnet.pdf') if False else None
    await A.screenshot(path='pb_print.png',full_page=True); await A.emulate_media(media='screen')
    print('screen hidden', await A.evaluate("getComputedStyle($('#printArea')).display"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
