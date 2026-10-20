"""v10.0 : Foulée Suivi (page famille multi-personnes : ajout par lien, statuts, carte, alerte, téléphone, état vide) et « Mes proches en direct » dans Foulée (lien #suivre=, carte sur l'accueil, liste, lien famille groupé)."""
import os, json, subprocess, time
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio
from playwright.async_api import async_playwright
G1='a'*32; G2='b'*32
NOW=int(time.time()*1000)
DATA={G1:{'v':1,'pseudo':'Lucas','st':'run','name':'Footing','t0':NOW-1800e3,'upd':NOW-30e3,'el':1770,'dist':5230,'pos':[45.91,6.12],'trk':[[45.9,6.1],[45.905,6.11],[45.91,6.12]],'route':None,'rest':2300,'eta':NOW+900e3,'sos':False},
      G2:{'v':1,'pseudo':'Christophe','st':'fini','name':'Sortie longue','t0':NOW-86400e3,'upd':NOW-80000e3,'el':5400,'dist':16200,'pos':[45.8,6.0],'trk':[[45.79,6.0],[45.8,6.0]],'route':None,'rest':None,'eta':None,'sos':False}}
async def gh(route):
    u=route.request.url;g=u.rstrip('/').split('/')[-1]
    if g in DATA: await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'files':{'foulee-live.json':{'content':json.dumps(DATA[g])}}}));return
    await route.fulfill(status=404,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{}')
async def leaflet(route):
    u=route.request.url;f='assets/leaflet.css' if u.endswith('.css') else 'assets/leaflet.js'
    await route.fulfill(status=200,content_type='text/css' if f.endswith('css') else 'application/javascript',body=open(os.path.join(APP,'tests',f),encoding='utf-8').read())
async def setup(pg):
    await pg.route('https://fonts.**',lambda r:r.abort()); await pg.route('https://api.github.com/**',gh); await pg.route('https://cdnjs.cloudflare.com/ajax/libs/leaflet/**',leaflet); await pg.route('https://*.tile.opentopomap.org/**',lambda r:r.abort())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    W=await ctx.new_page(); W.on('pageerror',lambda x:errs.append('W '+str(x))); await setup(W)
    await W.goto('http://127.0.0.1:8765/suivi.html'); await W.wait_for_timeout(600)
    print('empty', await W.evaluate("document.querySelector('.empty')?document.querySelector('.empty b').textContent:'no'"))
    await W.goto(f'http://127.0.0.1:8765/suivi.html#add={G1}&n=Lucas|add={G2}&n=Christophe'); await W.wait_for_timeout(1200)
    print('people', await W.evaluate("JSON.stringify(P.map(x=>[x.n,x.g.slice(0,4)]))"), 'hash cleared', await W.evaluate("location.hash===''"))
    print('header', await W.evaluate("document.querySelector('#hs').textContent"))
    print('cards', await W.evaluate("[...document.querySelectorAll('.p')].map(c=>c.querySelector('b').textContent+':'+c.querySelector('.badge').textContent).join(' | ')"))
    print('lucas grid', await W.evaluate("document.querySelector('.p .g').innerText.replace(/\\n/g,' ')"), 'markers', await W.evaluate("document.querySelectorAll('.leaflet-marker-icon').length"))
    await W.screenshot(path='v100_suivi.png',full_page=True)
    DATA[G1]['sos']=True; DATA[G1]['st']='alert'; DATA[G1]['upd']=int(time.time()*1000)
    await W.evaluate("tick(true)"); await W.wait_for_timeout(600)
    print('alert', await W.evaluate("!!document.querySelector('.p.alert')"), await W.evaluate("document.querySelector('.alertbox')&&document.querySelector('.alertbox').textContent.slice(0,40)"))
    await W.evaluate("openEdit(P.findIndex(x=>x.n==='Lucas'))"); await W.fill('#et','06 11 22 33 44'); await W.locator('#shb .btn.pri').click(); await W.wait_for_timeout(200)
    print('call btn', await W.evaluate("!!document.querySelector('a[href^=\"tel:0611223344\"]')"))
    await W.screenshot(path='v100_alert.png',full_page=True)
    await W.reload(); await W.wait_for_timeout(1000); print('persisted', await W.evaluate("P.length"))
    # Foulée : mes proches
    DATA[G1]['sos']=False; DATA[G1]['st']='run'
    A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append('A '+str(x))); await setup(A)
    await A.goto(f'http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();renderAll()"); await A.evaluate(f"location.hash='suivre={G1}&n=Lucas'"); await A.wait_for_timeout(1500)
    print('follow', await A.evaluate("JSON.stringify(S.follow)"), 'sheet', await A.evaluate("$('#sheetBody').innerText.includes('Mes proches en direct')"))
    await A.evaluate("closeSettings();FW.at=0;showTab('today')"); await A.wait_for_timeout(1200)
    print('today card', await A.evaluate("$('[data-page=today] .fw-c')?$('[data-page=today] .fw-c').innerText.replace(/\\n/g,' ').slice(0,120):'none'"))
    await A.locator('[data-page=today] .fw-c').screenshot(path='v100_card.png')
    await A.evaluate(f"S.liveGist='{G2}';save()"); print('family link', (await A.evaluate("fwLink(true)")).split('suivi.html')[1][:90])
    print('live url', (await A.evaluate("liveUrl()")).split('/')[-1][:40])
    await A.evaluate("openFollow(true)"); await A.screenshot(path='v100_follow.png',full_page=True)
    print('synced', await A.evaluate("'follow' in syncPayload().data"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
