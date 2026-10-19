"""v8.2 : design system « pro » (Nuit pro + Sport corail + Inter par défaut, migration de l'ancien défaut), anneaux de la semaine, dernière activité (Strava / fichier), infobulles des graphiques, écran partagé de l'analyse sur iPad / Mac."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
D=os.path.join(APP,'tests','assets')+'/'
async def page(br,vw,vh,init=None):
    ctx=await br.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2 if vw<600 else 1)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    if init: await A.add_init_script(init)
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
    await A.route('https://*.tile.opentopomap.org/**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(200)
    return ctx,A,errs
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch()
    # migration : ancien défaut → nouveau ; choix personnalisé conservé
    ctx,A,errs=await page(br,390,844,"localStorage.setItem('foulee_look',JSON.stringify({th:'sombre',pal:'alpin',font:'sport'}))")
    print('migrated', await A.evaluate("JSON.stringify(lookGet())"), await A.evaluate("getComputedStyle(document.body).backgroundColor"), await A.evaluate("cssv('--pT')"))
    await ctx.close()
    ctx,A,errs=await page(br,390,844,"localStorage.setItem('foulee_look',JSON.stringify({th:'clair',pal:'ocean',font:'lisible'}))")
    print('kept', await A.evaluate("lookGet().th+'/'+lookGet().pal+'/'+lookGet().font")); await ctx.close()
    # iPhone : tableau de bord
    ctx,A,errs=await page(br,390,844)
    await A.evaluate("loadDemo();renderAll();showTab('today')"); await A.wait_for_timeout(700)
    print('rings', await A.evaluate("document.querySelectorAll('[data-page=today] .wr-fg').length"), await A.evaluate("[...document.querySelectorAll('[data-page=today] .wr-v')].map(e=>e.textContent).join(' | ')"))
    print('last', await A.evaluate("$('[data-page=today] .la-t').textContent"), 'route', await A.evaluate("!!$('[data-page=today] .la-route polyline')"), 'prev', await A.evaluate("document.querySelectorAll('[data-page=today] .la-prev').length"))
    await A.screenshot(path='p_today.png'); await A.screenshot(path='p_today_full.png',full_page=True)
    # fichier importé plus récent → en tête
    await A.evaluate("S.imports=[{id:'imp1',name:'Trail des Crêtes',date:new Date().toISOString(),km:21.4,mov:9000,up:820,dn:810,ll:[[45.9,6.1],[45.91,6.12],[45.92,6.11],[45.9,6.1]],s:{d:[0,1000],z:[500,520],t:[0,300],hr:null}}];renderAll()")
    print('last file', await A.evaluate("$('[data-page=today] .la-t').textContent"), await A.evaluate("$('[data-page=today] .src').textContent"))
    # infobulle
    await A.evaluate("showTab('forme')"); await A.wait_for_timeout(500)
    g=A.locator('[data-page=forme] .chart [data-tip]').first
    await g.dispatch_event('pointerdown',{'clientX':200,'clientY':400,'pointerType':'touch'}); await A.wait_for_timeout(200)
    print('tip', await A.evaluate("$('#tip').classList.contains('on')"), await A.evaluate("$('#tip').textContent"))
    await A.screenshot(path='p_forme.png')
    for t in ['plan','renfo','sports','courses','histo','analyse','suivi','plus']:
        await A.evaluate(f"showTab('{t}')"); await A.wait_for_timeout(60)
        if await A.evaluate("document.documentElement.scrollWidth>innerWidth+1"): print('OVERFLOW',t)
    await A.evaluate("showTab('plan')"); await A.wait_for_timeout(500); await A.screenshot(path='p_plan.png')
    await A.evaluate("openSettings()"); await A.wait_for_timeout(500); await A.screenshot(path='p_settings.png'); await A.evaluate("closeSettings()")
    print('phone ERR',errs); await ctx.close()
    # iPad : écran partagé
    ctx,A,errs=await page(br,1194,834)
    await A.evaluate("loadDemo();renderAll();showTab('today')"); await A.wait_for_timeout(700); await A.screenshot(path='p_ipad_today.png')
    rid=await A.evaluate("getRuns()[0].id"); await A.evaluate(f"openAct({rid})"); await A.wait_for_timeout(900)
    print('split', await A.evaluate("getComputedStyle($('#actBody')).gridTemplateColumns"), 'map', await A.evaluate("Math.round($('#actMap').getBoundingClientRect().width)"), 'right', await A.evaluate("Math.round($('#actBody>.act-in').getBoundingClientRect().left)"))
    await A.screenshot(path='p_ipad_act.png'); await A.evaluate("closeAct()")
    await A.evaluate("lookSet('th','clair')"); await A.wait_for_timeout(400); await A.screenshot(path='p_ipad_clair.png')
    print('ipad ERR',errs); await ctx.close()
    await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
