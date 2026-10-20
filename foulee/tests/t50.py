"""v9.8 : analyse vidéo de la foulée (images rapprochées, outil coach simulé), survol 3D (MapLibre local, animation, profil), ton année Foulée (story, image), coach vocal mains libres (commandes, douleur, question au coach)."""
import os, json, subprocess
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
NM='/tmp/claude-0/v95/node_modules/maplibre-gl/dist/'
import asyncio, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;const _dn=Date.now.bind(Date);window._dn=_dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
GAIT={"visible":True,"qualite_video":"Bon cadrage de profil.","note":6,"resume":"Foulée régulière mais pose du pied devant le corps.","attaque":"talon","surenjambee":"Pied posé 25 cm devant les hanches","buste":"Légèrement cassé aux hanches","genou_impact":"Genou presque tendu au contact","bras":"Bras croisés devant le corps","oscillation":"moyen","cadence":"basse (< 160)","points_ok":["Regard loin devant"],"corrections":[{"image":5,"probleme":"Surenjambée","correction":"Pas plus courts, pieds sous les hanches","risque":"Chocs sur genoux et tibias"}],"exercices":["calf","bulg","rdl","inconnu"],"consigne_cle":"Petits pas rapides"}
async def claude(route):
    b=json.loads(route.request.post_data)
    if b.get('tools'):out={"content":[{"type":"tool_use","id":"t","name":"analyse_foulee","input":GAIT}],"stop_reason":"tool_use"}
    else:out={"content":[{"type":"text","text":"Ralentis un peu dans la montée et bois maintenant."}],"stop_reason":"end_turn"}
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(out))
async def mlib(route):
    u=route.request.url;f=NM+('maplibre-gl.css' if u.endswith('.css') else 'maplibre-gl.js')
    await route.fulfill(status=200,content_type='text/css' if u.endswith('.css') else 'application/javascript',body=open(f,encoding='utf-8').read())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(args=['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist']); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.anthropic.com/**',claude); await A.route('https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/**',mlib)
    await A.route('https://server.arcgisonline.com/**',lambda r:r.abort()); await A.route('https://s3.amazonaws.com/**',lambda r:r.abort()); await A.route('https://*.tile.opentopomap.org/**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();renderAll();setKey('sk-ant-test');S.mediaConsent=1;save()"); await A.wait_for_timeout(200)
    # --- foulée
    await A.evaluate("openGait()"); await A.locator('#sheetBody input[type=file]').set_input_files(os.path.join(APP,'tests/assets/foulee_test_vid.webm')); await A.wait_for_timeout(4000)
    print('frames', await A.evaluate("GX.frames?GX.frames.length:GX.err"))
    if await A.evaluate("!!GX.frames"):
        await A.locator('#sheetBody button:has-text("Analyser ma foulée")').click(); await A.wait_for_timeout(800)
        print('gait', await A.evaluate("JSON.stringify({note:GX.res.note,att:GX.res.attaque,ex:GX.res.ex,saved:(S.gait||[]).length})"), 'chips', await A.evaluate("document.querySelectorAll('#sheetBody .chips .chip').length"))
        await A.screenshot(path='v98_gait.png',full_page=True)
    await A.evaluate("closeSettings()")
    # --- survol 3D
    pts=[[45.9+i*0.0006,6.1+0.0004*((i//20)%2*(i%20)),500+(i%60)*8,i*70] for i in range(200)]
    await A.evaluate("pts=>{const d=new Date();d.setDate(d.getDate()+10);S.race={name:'Trail des Crêtes',date:iso(d),km:14,dp:900,gpx:{pts}};save();}",pts)
    await A.evaluate("fly3d(flySrcRace())"); await A.wait_for_timeout(5000)
    print('fly', await A.evaluate("JSON.stringify({on:$('#fly').classList.contains('on'),lib:!!window.maplibregl,p:FLY?Math.round(FLY.p*1000)/1000:null,info:$('#flyInfo')&&$('#flyInfo').textContent,prof:!!$('#flyProf svg'),len:FLY?Math.round(FLY.len):null})"))
    await A.screenshot(path='v98_fly.png')
    await A.evaluate("flySpeed();flyToggle()"); p1=await A.evaluate("FLY&&FLY.p"); await A.wait_for_timeout(600); print('paused', await A.evaluate("FLY&&FLY.p")==p1, await A.evaluate("$('#flySp').textContent"))
    await A.evaluate("flyClose()"); print('closed', await A.evaluate("!$('#fly').classList.contains('on')&&FLY===null"))
    # --- année
    await A.evaluate("openWrapped(2026)"); await A.wait_for_timeout(300)
    print('wrapped', await A.evaluate("WR.sl.length"), await A.evaluate("WR.sl.map(x=>x.k).join(',')"))
    await A.screenshot(path='v98_wr0.png')
    await A.evaluate("wrGo(1)"); await A.wait_for_timeout(700); print('slide2', await A.evaluate("$('#wrap .wr-big').textContent+' '+$('#wrap .wr-t').textContent")); await A.screenshot(path='v98_wr1.png')
    await A.evaluate("wrGo(1);wrGo(1)"); await A.wait_for_timeout(700); await A.screenshot(path='v98_wr3.png')
    await A.evaluate("wrShare()"); await A.wait_for_timeout(900); print('wr img', await A.evaluate("window.__wrImg")); await A.evaluate("wrClose()")
    # --- coach mains libres
    await A.evaluate("window.__now=_dn();liveFree()"); await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(300)
    await A.evaluate("""(()=>{let t=window.__now;for(let i=1;i<=40;i++){t+=4000;window.__now=t;grFeed({t,lat:45.9+i*12/111320,lon:6.1,acc:5});}grTick();})()""")
    print('mic btn', await A.evaluate("!!$('#grBody .gc-b')"))
    for t in ['Où j’en suis ?','pause','reprends','j’ai un peu mal au mollet','Est-ce que je dois boire ?']:
        await A.evaluate("window.__said=[]"); r=await A.evaluate("t=>gcHandle(t)",t); await A.wait_for_timeout(300)
        print('gc', t, '→', r, '|', ' / '.join(await A.evaluate("window.__said"))[:110])
    print('pain saved', await A.evaluate("JSON.stringify(S.check[iso(new Date())].pain)"), 'paused', await A.evaluate("GR.paused"))
    await A.evaluate("grMonoSet(true)"); print('mono mic', await A.evaluate("!!$('#grBody .gc-b')")); await A.screenshot(path='v98_mono.png')
    await A.evaluate("grStop(false);$('#grv').classList.remove('on');window.__now=null")
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
