"""v12.0 : boucle sur sentiers (BRouter simulé), course d'orientation (balises GPS, ordre, partage, résultat), plan de course + bracelet PDF, ravito guidé (annonces, Pris ✓, bilan), le bon créneau (météo simulée, carte Aujourd'hui), tapis roulant (blocs, séance guidée), agenda .ics (lecture, créneaux libres, proposition, application), coach de descente (démo)."""
import asyncio, json, math, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
HOME=(49.30,2.45)
NM='/tmp/claude-0/v95/node_modules'
async def lib(route):
    u=route.request.url
    f=NM+('/jspdf/dist/jspdf.umd.min.js' if 'autotable' not in u else '/jspdf-autotable/dist/jspdf.plugin.autotable.min.js')
    await route.fulfill(status=200,content_type='application/javascript',body=open(f,encoding='utf-8').read())
def dest(la,lo,km,b):
    R=6371;d=km/R;b=math.radians(b);a1=math.radians(la);o1=math.radians(lo)
    a2=math.asin(math.sin(a1)*math.cos(d)+math.cos(a1)*math.sin(d)*math.cos(b));o2=o1+math.atan2(math.sin(b)*math.sin(d)*math.cos(a1),math.cos(d)-math.sin(a1)*math.sin(a2));return math.degrees(a2),math.degrees(o2)
BR=[]
async def brouter(route):
    u=route.request.url;BR.append(u);ll=[tuple(map(float,x.split(','))) for x in u.split('lonlats=')[1].split('&')[0].split('|')]
    co=[];
    for i in range(len(ll)-1):
        for k in range(20):
            f=k/20;lo=ll[i][0]+(ll[i+1][0]-ll[i][0])*f;la=ll[i][1]+(ll[i+1][1]-ll[i][1])*f;co.append([lo,la,100+40*math.sin(len(co)/12)])
    co.append([ll[-1][0],ll[-1][1],100])
    L=0
    for i in range(1,len(co)):
        L+=6371000*math.acos(min(1,math.sin(math.radians(co[i-1][1]))*math.sin(math.radians(co[i][1]))+math.cos(math.radians(co[i-1][1]))*math.cos(math.radians(co[i][1]))*math.cos(math.radians(co[i][0]-co[i-1][0]))))
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'track-length':str(round(L*1.25)),'filtered ascend':'180'},'geometry':{'type':'LineString','coordinates':co}}]}))
def hourly():
    t=[];at=[];pp=[];w=[]
    for d in range(3):
        ds=time.strftime('%Y-%m-%d',time.localtime(time.time()+d*86400))
        for h in range(24): t.append(f'{ds}T{h:02d}:00');at.append(round(9+15*max(0,math.sin((h-8)/12*math.pi))));pp.append(5);w.append(8)
    return {'time':t,'apparent_temperature':at,'precipitation_probability':pp,'wind_speed_10m':w}
async def meteo(route):
    u=route.request.url
    if '/elevation' in u:
        n=len(u.split('latitude=')[1].split('&')[0].split(','));await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'elevation':[100+i*15 for i in range(n)]}));return
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'hourly':hourly()}))
def d8(n,h): return time.strftime('%Y%m%d',time.localtime(time.time()+n*86400))+f'T{h:02d}0000'
ICS="BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:"+d8(1,6)+"\r\nDTEND:"+d8(1,21)+"\r\nSUMMARY:Garde\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART:"+d8(2,8)+"\r\nDTEND:"+d8(2,18)+"\r\nRRULE:FREQ=DAILY;COUNT=2\r\nSUMMARY:Boulot\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
async def setup(pg):
    await pg.add_init_script(INIT)
    for u in ['https://fonts.**','https://api.anthropic.com/**','https://overpass**']: await pg.route(u,lambda r:r.abort())
    await pg.route('**/*jspdf*',lib)
    await pg.route('https://brouter.de/**',brouter); await pg.route('https://*open-meteo.com/**',meteo)
    await pg.route('https://cal.test/**',lambda r:r.fulfill(status=200,content_type='text/calendar',headers={'access-control-allow-origin':'*'},body=ICS))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':HOME[0],'longitude':HOME[1]},permissions=['geolocation'],accept_downloads=True)
    A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append(str(x))); await setup(A)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();S.settings.poids=72;save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    print('version', await A.evaluate("APP_VER"), 'plus', await A.evaluate("['loop','band','tread','orient','agenda','slot','fuelg','descent'].map(k=>PLUSI.some(x=>x.k===k)?k:'!'+k).join(',')"))
    # --- 1. boucle
    await A.evaluate("openLoop()"); await A.fill('#lp_km','10'); await A.fill('#lp_dp','200'); await A.click('#lp_go'); await A.wait_for_timeout(1500)
    print('loop calls', len(BR), 'profil', 'hiking-mountain' in BR[0], 'cartes', await A.evaluate("document.querySelectorAll('#lp_res .lp-c').length"), '|', await A.evaluate("[...document.querySelectorAll('#lp_res .lp-c .tag')].map(x=>x.textContent).join(' / ')"))
    await A.screenshot(path='v120_loop.png')
    await A.evaluate("loopKeep(0,1)"); await A.wait_for_timeout(300)
    print('loop suivie', await A.evaluate("!!(GR.route&&GR.route.id.startsWith('loop:'))"), await A.evaluate("Math.round(GR.route.len)"), 'gardée', await A.evaluate("loopsGet().length"), 'source', await A.evaluate("routeSrcs().some(x=>x.id.startsWith('loop:'))"))
    await A.evaluate("grClose()"); await A.wait_for_timeout(100)
    gpx=await A.evaluate("gpxOf('t',loopsGet()[0].pts).slice(0,120)"); print('gpx', gpx.replace('\n',' ')[:90])
    # --- 2. orientation
    await A.evaluate("""(()=>{ORE.edit={id:'or1',n:'Parcours du bois',cps:[],order:true,res:[]};orEditDraw();})()"""); await A.wait_for_timeout(600)
    await A.evaluate(f"orAdd([{HOME[0]+0.002},{HOME[1]}]);orAdd([{HOME[0]+0.002},{HOME[1]+0.003}]);orAdd([{HOME[0]},{HOME[1]+0.003}])"); await A.wait_for_timeout(100)
    print('balises', await A.evaluate("ORE.edit.cps.length"), await A.evaluate("$('#orCps').innerText.split('\\n').pop()"))
    await A.screenshot(path='v120_orient_edit.png'); await A.evaluate("orSave()"); await A.wait_for_timeout(150)
    link=await A.evaluate("(()=>{const p=orList()[0];return 'index.html#orient='+ivEnc({id:p.id,n:p.n,order:p.order,cps:p.cps,from:'Papa'})})()")
    await A.evaluate("orStart('or1')"); await A.wait_for_timeout(300)
    await A.evaluate(f"orFeed({{lat:{HOME[0]+0.0021},lon:{HOME[1]},acc:8}})")  # balise 1
    await A.evaluate(f"orFeed({{lat:{HOME[0]},lon:{HOME[1]+0.003},acc:8}})")  # balise 3 hors ordre → pas validée
    print('ordre', await A.evaluate("ORE.run.got.join(',')"), await A.evaluate("$('#orx .or-next').innerText.replace(/\\n/g,' · ')"))
    await A.evaluate(f"orFeed({{lat:{HOME[0]+0.002},lon:{HOME[1]+0.003},acc:60}})"); print('imprécis ignoré', await A.evaluate("ORE.run.got.length"))
    await A.evaluate(f"orFeed({{lat:{HOME[0]+0.002},lon:{HOME[1]+0.003},acc:8}})"); await A.evaluate(f"orFeed({{lat:{HOME[0]},lon:{HOME[1]+0.0031},acc:8}})"); await A.wait_for_timeout(200)
    print('fini', await A.evaluate("ORE.run.done"), await A.evaluate("orList()[0].res.length"), '| voix', await A.evaluate("__said.filter(x=>/Balise|balise/.test(x)).slice(-2).join(' / ')"))
    await A.screenshot(path='v120_orient_run.png'); await A.evaluate("orStop()")
    # partage reçu par le fils
    B=await ctx.new_page(); B.on('pageerror',lambda x:errs.append('B '+str(x))); await setup(B)
    await B.goto('http://127.0.0.1:8765/'+link); await B.wait_for_timeout(2600)
    print('reçu', await B.evaluate("orList().map(p=>p.n+' '+p.cps.length+' de '+p.from).join(',')"), 'hash nettoyé', await B.evaluate("location.hash===''"))
    res=await B.evaluate("'index.html#orres='+ivEnc({id:'or1',who:'Lucas',t:1325,at:Date.now()})"); await B.close()
    await A.goto('http://127.0.0.1:8765/'+res); await A.wait_for_timeout(2600)
    print('résultat reçu', await A.evaluate("orList()[0].res.map(r=>r.who+' '+r.t).join(',')"))
    # --- 3. bracelet
    await A.evaluate("S.race={name:'Trail des Lacs',date:iso(new Date(Date.now()+30*864e5)),km:21,dp:650,aid:[8,15]};save();renderAll();openPaceBand()"); await A.wait_for_timeout(200)
    print('bracelet', await A.evaluate("document.querySelectorAll('#sheetBody .pb-r').length"), 'ravitos', await A.evaluate("document.querySelectorAll('#sheetBody .pb-r.aid').length"), '|', await A.evaluate("$('#sheetBody .pb-r').innerText.replace(/\\n/g,' ')"))
    await A.screenshot(path='v120_band.png')
    try:
        async with A.expect_download(timeout=15000) as dl: await A.evaluate("pbPdf()")
        d=await dl.value; print('pdf', d.suggested_filename)
    except Exception as e: print('pdf non testable ici (réseau)', str(e)[:60])
    await A.evaluate("closeSettings();showTab('courses')"); print('héros courses', await A.evaluate("$('[data-page=courses] .f-pghero').innerText.includes('Bracelet')"))
    # --- 4. ravito
    await A.evaluate("grOpen('r0l');GR.steps=[{n:'Sortie longue',k:'run',t:5400,lo:380,hi:420}];GR.on=true;GR.paused=false;GR.t0=Date.now();GR.acc=0;fuelInit()")
    print('ravito plan', await A.evaluate("GR.fuel?GR.fuel.plan.length+' prises, '+GR.fuel.min+' min':'aucun'"))
    await A.evaluate("__said.length=0;fuelTick(21);grDraw()"); print('annonce', await A.evaluate("__said.join(' / ')"), '| ligne', await A.evaluate("($('#grBody .fu-l')||{innerText:''}).innerText"))
    await A.evaluate("fuelOk();fuelTick(41)"); await A.evaluate("GR.on=false;grDraw()"); print('bilan', await A.evaluate("($('#grBody .fu-l')||{innerText:''}).innerText"))
    await A.evaluate("grClose()")
    await A.evaluate("grOpen('r0r');GR.steps=[{n:'Footing',k:'run',t:1800,lo:380,hi:420}];fuelInit()"); print('court sans ravito', await A.evaluate("GR.fuel===null")); await A.evaluate("grClose()")
    # --- 5. créneau
    await A.evaluate("S.settings.loc=[49.3,2.45];SLW=null;try{localStorage.removeItem('foulee_slotwx')}catch(e){};save()"); await A.evaluate("slotLoad(true)"); await A.wait_for_timeout(300)
    await A.evaluate("renderToday();showTab('today')"); await A.wait_for_timeout(200)
    print('créneau', await A.evaluate("($('[data-page=today] .f-slot')||{innerText:'(aucune séance à venir)'}).innerText.replace(/\\n/g,' · ')"))
    print('slotBest', await A.evaluate("JSON.stringify(slotBest(SLW.H,iso(new Date(Date.now()+864e5)),90))"))
    # --- 6. tapis
    await A.evaluate("TM.src='race';TM.part='all';openTread()"); await A.wait_for_timeout(150)
    print('tapis', await A.evaluate("TM.B.length+' blocs, pentes '+[...new Set(TM.B.map(b=>b.inc))].sort((a,b)=>a-b).join('/')+' %, vitesses '+Math.min(...TM.B.map(b=>b.kmh))+'–'+Math.max(...TM.B.map(b=>b.kmh))"))
    await A.evaluate("TM.part='climb';openTread()"); print('montée', await A.evaluate("TM.B.length+' blocs, '+fmtH(TM.B.reduce((a,b)=>a+b.sec,0))"))
    await A.screenshot(path='v120_tread.png')
    await A.evaluate("tmStart()"); await A.wait_for_timeout(1200); print('tapis guidé', await A.evaluate("$('#tmx .tm-big').innerText.replace(/\\n/g,' ')"), '|', await A.evaluate("__said.slice(-1)[0]"))
    await A.evaluate("TM.run.acc=TM.B[0].sec*1000+500;TM.run.t0=Date.now();tmTick()"); print('bloc 2', await A.evaluate("TM.run.i"), await A.evaluate("__said.slice(-1)[0]")); await A.evaluate("tmStop()")
    # --- 7. agenda
    await A.evaluate("localStorage.setItem('foulee_ics','https://cal.test/a.ics');openAgenda()"); await A.wait_for_timeout(100)
    await A.evaluate("agRun()"); await A.wait_for_timeout(500)
    print('agenda busy', await A.evaluate("Object.keys(S.agenda.busy).length+' jours occupés · '+JSON.stringify(S.agenda.busy[iso(new Date(Date.now()+864e5))])"))
    print('trop chargés', await A.evaluate("AG.res.busyDays.map(d=>parseISO(d).getDay()).join(',')"), '| décisions', await A.evaluate("AG.res.decisions.map(x=>x.action+(x.jour?'@'+x.jour.slice(5):'')+(x.slot?' '+agHm(x.slot[0]):'')).join(' · ')"))
    print('aucune séance un jour occupé', await A.evaluate("AG.res.decisions.filter(x=>x.action!=='annuler'&&AG.res.busyDays.includes(x.jour)).length"))
    await A.screenshot(path='v120_agenda.png')
    rr=await A.evaluate("(()=>{const n=AG.res.decisions.filter(x=>x.action!=='garder').length;agApply();return n+' / mv '+Object.keys(S.mv||{}).length})()"); print('appliqué', rr)
    print('ics tz', await A.evaluate("(()=>{const e=icsParse('BEGIN:VEVENT\\nDTSTART;TZID=Europe/Paris:20261105T090000\\nDTEND;TZID=Europe/Paris:20261105T100000\\nEND:VEVENT',new Date(2026,10,1),new Date(2026,10,10));return e.length+' '+e[0].s.toISOString()})()"))
    print('ics weekly', await A.evaluate("icsParse('BEGIN:VEVENT\\nDTSTART:20261102T180000Z\\nDTEND:20261102T190000Z\\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE\\nEXDATE:20261104T180000Z\\nEND:VEVENT',new Date(2026,10,1),new Date(2026,10,12)).map(e=>e.s.toISOString().slice(5,10)).join(',')"))
    # --- 8. descente
    await A.evaluate("closeSettings();showTab('analyse')"); await A.wait_for_timeout(200)
    print('descente carte', await A.evaluate("($('[data-page=analyse] .f-ds')||{innerText:'absente'}).innerText.replace(/\\n/g,' · ').slice(0,160)"))
    print('détection', await A.evaluate("(()=>{const n=60,d=[],alt=[],t=[];for(let i=0;i<n;i++){d.push(i*50);alt.push(i<30?100+i*5:250-(i-30)*5);t.push(i<30?i*30:900+(i-30)*15);}const L=dsDetect({d,alt,t});return L.length+' · '+L.map(x=>x.drop+' m '+Math.round(x.g*100)+' % '+fmtPace(x.pace)+' note '+dsScore(x,400)).join(' | ')})()"))
    await A.evaluate("openDescent()"); await A.wait_for_timeout(150); await A.screenshot(path='v120_descent.png'); print('fiche', await A.evaluate("$('#sheetBody').innerText.includes('Exercices')"))
    await A.evaluate("closeSettings();showTab('plus')"); await A.wait_for_timeout(150)
    print('espace', await A.evaluate("['loop','band','tread','orient','agenda','slot','fuelg','descent'].map(k=>!!$('[data-page=plus] .prow[data-k='+k+']')).join(',')"))
    print('overflow', await A.evaluate("document.documentElement.scrollWidth>innerWidth"))
    print('ERR', errs); await br.close()
asyncio.run(m())
