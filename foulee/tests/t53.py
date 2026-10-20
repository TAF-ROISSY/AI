"""v10.1 : mode jeune (séances + règles du coach), semaine partagée, stats famille, sortie à deux (écart annoncé), mode vacances (jours de voyage, carte météo, géocodage), tests d'envoi (SMS de test, écran d'alerte TEST sans publication, test d'alerte dans Foulée Suivi)."""
import os, json, subprocess, time
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;const _dn=Date.now.bind(Date);window._dn=_dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
SON='c'*32; NOW=int(time.time()*1000); GH={'posts':[],'patch':0}; CL={}
SONLIVE={'v':1,'pseudo':'Lucas','st':'run','name':'Footing','t0':NOW-600e3,'upd':NOW,'el':600,'dist':3000,'pos':[45.93,6.1],'trk':[[45.9,6.1],[45.93,6.1]],'rest':None,'eta':None,'sos':False}
SONWEEK={'v':1,'pseudo':'Lucas','jeune':True,'sem':{'n':4,'f':2,'km':14.5,'dp':220,'list':[{'d':'2026-10-19','t':'Footing 40 min','ok':True},{'d':'2026-10-21','t':'Côtes courtes','ok':False}]},'forme':{'sc':81,'t':'Feu vert'},'douleurs':[{'d':'2026-10-19','z':'Genou','lv':1}],'saison':{'an':2026,'km':640,'dp':9100,'xp':8000,'lvl':9},'course':None,'maj':NOW}
async def gh(route):
    r=route.request;u=r.url
    if r.method=='POST' and u.endswith('/gists'): GH['posts'].append(json.loads(r.post_data)['files']); await route.fulfill(status=201,content_type='application/json',body=json.dumps({'id':'d'*32}));return
    if r.method=='PATCH': GH['patch']+=1; GH['last']=json.loads(r.post_data)['files']; await route.fulfill(status=200,content_type='application/json',body='{}');return
    if SON in u:
        SONLIVE['upd']=int(time.time()*1000)
        await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'files':{'foulee-live.json':{'content':json.dumps(SONLIVE)},'foulee-week.json':{'content':json.dumps(SONWEEK)}}}));return
    await route.fulfill(status=404,content_type='application/json',body='{}')
async def meteo(route):
    u=route.request.url
    if 'geocoding' in u: await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'results':[{'name':'Bangkok','country':'Thaïlande','admin1':'Bangkok','latitude':13.75,'longitude':100.5,'timezone':'Asia/Bangkok'}]}));return
    from datetime import date,timedelta
    d0=date.today();days=[(d0+timedelta(i)).isoformat() for i in range(3)];hrs=[f"{d}T{h:02d}:00" for d in days for h in range(24)]
    T=[26+6*__import__('math').sin((h%24-9)/24*6.28) for h in range(72)]
    body={'hourly':{'time':hrs,'temperature_2m':T,'relative_humidity_2m':[78]*72,'dew_point_2m':[23]*72},'daily':{'time':days,'sunrise':[d+'T06:12' for d in days],'sunset':[d+'T18:01' for d in days],'temperature_2m_max':[33,34,33]},'current':{'temperature_2m':30,'relative_humidity_2m':75,'dew_point_2m':24},'timezone':'Asia/Bangkok'}
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(body))
async def claude(route):
    CL['sys']=json.loads(route.request.post_data).get('system','')
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"text","text":"OK"}],"stop_reason":"end_turn"}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.github.com/**',gh); await A.route('https://*open-meteo.com/**',meteo); await A.route('https://api.anthropic.com/**',claude)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();setVC({token:'ghp_test'});renderAll()"); await A.wait_for_timeout(200)
    # mode jeune
    await A.evaluate("openYouth()"); print('youth sheet', await A.evaluate("$('#sheetBody').innerText.includes('Mode jeune')"))
    await A.evaluate("S.settings.jeune=true;save();closeSettings()")
    print('jeune', await A.evaluate("(()=>{for(let w=0;w<12;w++)for(let d=0;d<7;d++){const L=daySessions(w,d);const l=L.find(o=>/^r\\d+l$/.test(o.k));if(l){window.__jl=strip(l.s).slice(-40);}const s=L.find(o=>/^s\\d+[ABC]$/.test(o.k));if(s){window.__js=strip(s.s).slice(-50);}}return window.__jl+' | '+window.__js})()"))
    await A.evaluate("setKey('sk-ant-x');claude({system:'BASE',messages:[{role:'user',content:'test'}],max:50})"); await A.wait_for_timeout(300); print('coach rule', 'ATHLÈTE JEUNE' in CL.get('sys',''))
    # semaine partagée
    await A.evaluate("S.settings.shareWeek=true;save();weekPush(true)"); await A.wait_for_timeout(400)
    f=GH['posts'][-1] if GH['posts'] else {}; print('week push', sorted(f.keys()), 'gist', await A.evaluate("S.liveGist&&S.liveGist.slice(0,4)"))
    W=json.loads(f.get('foulee-week.json',{}).get('content','{}')); print('payload', W.get('sem',{}).get('n'), W.get('forme'), W.get('saison',{}).get('an'), W.get('jeune'))
    # suivi fils + semaine + famille
    await A.evaluate(f"fwAdd('{SON}','Lucas');fwFetch(true)"); await A.wait_for_timeout(600)
    await A.evaluate("openFollow(true)"); print('week line', await A.evaluate("$('#sheetBody .fw-wk summary')?$('#sheetBody .fw-wk summary').textContent:'none'"))
    print('famille', await A.evaluate("$('#sheetBody .fam')?$('#sheetBody .fam').innerText.replace(/\\n/g,' ').slice(0,160):'none'"))
    await A.screenshot(path='v101_follow.png',full_page=True); await A.evaluate("closeSettings()")
    # sortie à deux
    k=await A.evaluate("(()=>{for(let w=0;w<12;w++)for(let d=0;d<7;d++){const o=daySessions(w,d,'run').find(x=>/e$/.test(x.k)||/r$/.test(x.k));if(o)return o.k;}})()")
    await A.evaluate(f"grOpen('{k}')"); print('duo select', await A.evaluate("!!$('#grBody select option[value=\"{0}\"]'.replace('{0}','"+SON+"'))"))
    await A.evaluate(f"duoPick('{SON}');window.__now=_dn()"); await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(300)
    await A.evaluate("""(()=>{let t=window.__now;for(let i=1;i<=100;i++){t+=4000;window.__now=t;grFeed({t,lat:45.9+i*12/111320,lon:6.1,acc:5});}})()""")
    await A.evaluate("window.__now=null;window.__said=[];duoTick(true)"); await A.wait_for_timeout(500)
    print('duo', await A.evaluate("duoTxt(false)"), '| said', await A.evaluate("window.__said.join(' / ').slice(0,120)"))
    await A.evaluate("grDraw()"); print('duo line', await A.evaluate("$('#grBody .duo-l')&&$('#grBody .duo-l').textContent"))
    await A.screenshot(path='v101_duo.png'); await A.evaluate("grStop(false);$('#grv').classList.remove('on');window.__now=null")
    # vacances
    await A.evaluate("openTrip()"); await A.fill('#tp_q','Bangkok'); await A.evaluate("tripSearch()"); await A.wait_for_timeout(400); await A.locator('#tp_res .chip').first.click(); await A.wait_for_timeout(200)
    await A.evaluate("(()=>{let f=new Date(Date.now()-864e5);for(let i=1;i<6;i++){const x=new Date(Date.now()+i*864e5);if(daySessions(weekIdx(x),dayIdx(x)).length){f=x;break;}}const t=new Date(f.getTime()+6*864e5);$('#tp_f').value=iso(f);$('#tp_t').value=iso(t);})()"); await A.locator('#sheetBody button:has-text("Enregistrer")').click(); await A.wait_for_timeout(1200)
    print('trip', await A.evaluate("JSON.stringify(S.trip)"))
    print('travel day', await A.evaluate("(()=>{const dt=parseISO(S.trip.from);const L=daySessions(weekIdx(dt),dayIdx(dt));return L.length?L.map(o=>[!!o.cancel,strip(o.t).slice(0,20)].join(':')).join(','):'aucune séance'})()"))
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(800); print('trip card', await A.evaluate("$('[data-page=today] .trip')?$('[data-page=today] .trip').innerText.replace(/\\n/g,' ').slice(0,220):'none'"))
    await A.locator('[data-page=today] .trip').screenshot(path='v101_trip.png')
    # tests d'envoi
    await A.evaluate("S.settings.sosOn=true;S.settings.sosTel='06 12 34 56 78';S.settings.live=true;save();openLive()")
    print('sms test', await A.evaluate("decodeURIComponent([...document.querySelectorAll('#sheetBody a')].find(a=>a.textContent.includes('message de test')).getAttribute('href')).slice(0,90)"))
    await A.evaluate("S.settings.startMsg=true;S.settings.startName='Ma femme';S.settings.startTel='06 98 76 54 32';save();openLive()")
    await A.evaluate("S.settings.cmbStart='999';save()"); print('wa auto test', await A.evaluate("waAuto('06 98 76 54 32','999','[TEST] x')"), await A.evaluate("telIntl('06 98 76 54 32')"))
    await A.evaluate("S.settings.cmbStart='';save()")
    print('start test', await A.evaluate("decodeURIComponent([...document.querySelectorAll('#sheetBody a')].find(a=>a.textContent.includes('départ de test')).getAttribute('href')).slice(0,110)"))
    await A.screenshot(path='v101_live.png',full_page=True)
    k2=await A.evaluate("(()=>{for(let w=0;w<12;w++)for(let d=0;d<7;d++){const o=daySessions(w,d,'run').find(x=>/q$/.test(x.k));if(o)return o.k;}})()")
    await A.evaluate(f"closeSettings();grOpen('{k2}')"); await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(1200)
    print('start btn', await A.evaluate("$('#stMsg')?$('#stMsg').textContent+' → '+decodeURIComponent($('#stMsg').getAttribute('href')).split(/body=|text=/)[1].slice(0,90):'none'"))
    await A.evaluate("grStop(false);$('#grv').classList.remove('on')"); await A.wait_for_timeout(1200)
    n0=GH['patch']+len(GH['posts']); await A.evaluate("window.__now=_dn();sosTest()"); await A.wait_for_timeout(300); print('test overlay', await A.evaluate("$('#sos').innerText.includes('TEST')"))
    await A.evaluate("window.__now=_dn()+11000"); await A.wait_for_timeout(1400); print('test alert', await A.evaluate("LV.sos"), await A.evaluate("$('#sos').innerText.includes('rien n’a été publié')"), 'sms body', await A.evaluate("decodeURIComponent($('#sos a').getAttribute('href')).includes('[TEST')"), 'no alert published', 'alert' not in json.dumps(GH.get('last',{})))
    await A.screenshot(path='v101_sostest.png'); await A.evaluate("sosOk();window.__now=null"); print('cleared', await A.evaluate("!LV.test&&!LV.sos"))
    V=await ctx.new_page(); await V.route('https://cdnjs.cloudflare.com/**',lambda r:r.abort()); await V.goto('http://127.0.0.1:8765/suivi.html'); await V.wait_for_timeout(500)
    await V.locator('button:has-text("Tester une alerte")').click(); await V.wait_for_timeout(300); print('suivi test', await V.evaluate("window.__testAlert"), await V.evaluate("!!document.querySelector('.alertbox')"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
