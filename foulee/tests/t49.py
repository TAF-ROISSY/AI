"""v9.7 : LiveTrack (publication, alerte d'immobilité, SMS, page de suivi), météo par tronçon le jour J, niveaux / séries / badges / saison (et défis XP), risque de blessure."""
import os, json, subprocess
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;const _dn=Date.now.bind(Date);window._dn=_dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
LIVE={}
async def gh(route):
    r=route.request;u=r.url
    if r.method=='POST' and u.endswith('/gists'):
        f=json.loads(r.post_data)['files'];LIVE['last']=f;await route.fulfill(status=201,content_type='application/json',body=json.dumps({'id':'abc123'}));return
    if r.method=='PATCH':
        f=json.loads(r.post_data)['files'];LIVE['last']=f;LIVE['n']=LIVE.get('n',0)+1;await route.fulfill(status=200,content_type='application/json',body='{}');return
    if r.method=='GET' and '/gists/abc123' in u:
        await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'files':LIVE['last']}));return
    await route.fulfill(status=404,content_type='application/json',body='{}')
async def meteo(route):
    u=route.request.url;n=u.split('latitude=')[1].split('&')[0].count(',')+1
    hrs=[f"2026-10-{d:02d}T{h:02d}:00" for d in (25,26) for h in range(24)]
    one={'hourly':{'time':hrs,'temperature_2m':[8+h%24*0.6 for h in range(48)],'apparent_temperature':[6+h%24*0.6 for h in range(48)],'precipitation_probability':[55]*48,'precipitation':[0.4]*48,'wind_speed_10m':[32]*48,'weather_code':[61]*48}}
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps([one]*n if n>1 else one))
async def leaflet(route):
    u=route.request.url;f='assets/leaflet.css' if u.endswith('.css') else 'assets/leaflet.js'
    await route.fulfill(status=200,content_type='text/css' if f.endswith('css') else 'application/javascript',body=open(os.path.join(APP,'tests',f),encoding='utf-8').read())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.github.com/**',gh); await A.route('https://api.open-meteo.com/**',meteo)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    # ---- LiveTrack
    await A.evaluate("setVC({token:'ghp_test'});S.settings.live=true;S.settings.sosOn=true;S.settings.sosMin=3;S.settings.sosName='Annabelle';S.settings.sosTel='06 12 34 56 78';save();openLive()")
    print('live sheet', await A.evaluate("$('#sheetBody').innerText.includes('Alerte d’immobilité')")); await A.screenshot(path='v97_live.png',full_page=True)
    await A.evaluate("window.__now=_dn();liveFree()"); await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(600)
    print('started', await A.evaluate("GR.on"), 'gist', await A.evaluate("S.liveGist"), 'url', (await A.evaluate("liveUrl()")).split('/')[-1])
    await A.evaluate("""(()=>{let t=window.__now;for(let i=1;i<=60;i++){t+=4000;window.__now=t;grFeed({t,lat:45.9+i*12/111320,lon:6.1,acc:5});}grTick();})()""")
    await A.evaluate("livePush()"); await A.wait_for_timeout(300)
    P=json.loads(LIVE['last']['foulee-live.json']['content']); print('payload', P['st'], P['dist'], len(P['trk']), P['pos'] is not None, P['pseudo'])
    # immobile 3+ min
    await A.evaluate("""(()=>{let t=window.__now;const L=GR.pts[GR.pts.length-1];for(let i=0;i<20;i++){t+=10000;window.__now=t;grFeed({t,lat:L.lat+0.00001,lon:L.lon,acc:5});GR.fix={t,lat:L.lat+0.00001,lon:L.lon,acc:5};grTick();}})()""")
    print('sos ask', await A.evaluate("LV.sos"), await A.evaluate("$('#sos')&&$('#sos').classList.contains('on')"), any('Tout va bien' in x for x in await A.evaluate("window.__said")))
    await A.screenshot(path='v97_sos.png')
    await A.evaluate("window.__now=_dn()+3600e3"); await A.wait_for_timeout(1500)
    print('sos alert', await A.evaluate("LV.sos"), 'sms', await A.evaluate("decodeURIComponent($('#sos a').getAttribute('href')).slice(0,120)"))
    await A.wait_for_timeout(300); P=json.loads(LIVE['last']['foulee-live.json']['content']); print('pushed alert', P['st'], P['sos'])
    await A.screenshot(path='v97_alert.png')
    await A.evaluate("sosOk()"); print('ok', await A.evaluate("LV.sos"), await A.evaluate("!$('#sos').classList.contains('on')"))
    # viewer
    V=await ctx.new_page(); V.on('pageerror',lambda x:errs.append('V '+str(x))); await V.route('https://api.github.com/**',gh); await V.route('https://cdnjs.cloudflare.com/**',leaflet); await V.route('https://*.tile.opentopomap.org/**',lambda r:r.abort())
    await V.goto('http://127.0.0.1:8765/live.html#g=abc123'); await V.wait_for_timeout(1500)
    print('viewer', await V.evaluate("document.querySelector('#who').textContent"), '|', await V.evaluate("document.querySelector('#st').textContent"), '|', await V.evaluate("document.querySelector('#dist').textContent"), 'track', await V.evaluate("document.querySelectorAll('path.leaflet-interactive').length"))
    await V.screenshot(path='v97_viewer.png'); await V.close()
    await A.evaluate("grStop(true);$('#grv').classList.remove('on');window.__now=null"); await A.wait_for_timeout(400); P=json.loads(LIVE['last']['foulee-live.json']['content']); print('stop', P['st'])
    # ---- météo par tronçon
    pts=[[45.9+i*0.001,6.1,500+(i%40)*10,i*100] for i in range(301)]
    await A.evaluate("pts=>{S.race={name:'Trail des Crêtes',date:'2026-10-25',km:30,dp:1500,h:'8 h 30',gpx:{pts}};save();}",pts)
    await A.evaluate("openRaceDay()"); await A.wait_for_timeout(800)
    print('wx', await A.evaluate("$('#rdWx').innerText.replace(/\\n/g,' ').slice(0,260)"))
    print('wx cells', await A.evaluate("document.querySelectorAll('#rdWx .wx-c').length"))
    await A.locator('#rdWx').screenshot(path='v97_wx.png'); await A.evaluate("closeSettings()")
    # ---- niveaux
    print('xp', await A.evaluate("JSON.stringify({all:xpData().xp,season:xpSeason(),lvl:xpLvl(xpSeason()),streak:xpStreak(),badges:xpBadges().filter(b=>b[3]).map(b=>b[1])})"))
    await A.evaluate("showTab('suivi')"); await A.wait_for_timeout(200); print('xp card', await A.evaluate("!!$('#xpCard')"))
    await A.locator('#xpCard').screenshot(path='v97_xp.png')
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(150); print('xp mini', await A.evaluate("!!$('[data-page=today] .xp-mini')"), 'payload', await A.evaluate("JSON.stringify(defiPayload().saison)"))
    # ---- risque
    print('risk base', await A.evaluate("JSON.stringify((({sc,lv})=>({sc,lv}))(riskData()))"))
    await A.evaluate("(()=>{const t=iso(new Date());S.check=S.check||{};S.check[t]={fc:null,sore:2,mood:0,pain:[{z:'genou',lv:3}],t:Date.now()};S.sleep=S.sleep||{};for(let i=0;i<3;i++){const d=iso(new Date(Date.now()-i*864e5));S.sleep[d]={h:5.25,q:2,t:Date.now()};}save();renderAll();})()")
    R=await A.evaluate("JSON.stringify((({sc,lv,F,nx})=>({sc,lv,F:F.map(f=>f[1]),nx:nx&&nx.o.k}))(riskData()))"); print('risk', R)
    print('risk card today', await A.evaluate("!!$('[data-page=today] .risk')"))
    await A.locator('[data-page=today] .risk').screenshot(path='v97_risk.png')
    nx=json.loads(R)['nx']
    if nx: await A.evaluate(f"riskLight('{nx}')"); print('lightened', await A.evaluate(f"JSON.stringify(S.adj['{nx}'].action)"))
    await A.evaluate("showTab('forme')"); await A.wait_for_timeout(150); print('forme risk', await A.evaluate("!!$('[data-page=forme] .risk')"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
