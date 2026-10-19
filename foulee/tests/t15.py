import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, subprocess, time, base64
from playwright.async_api import async_playwright
FIG={"exercice_visible":True,"qualite_video":"ok","note":8,"resume":"Bon alignement global.","points_ok":["Bras verrouillés"],"corrections":[{"image":4,"probleme":"Dos cambré","correction":"Rentre les côtes","risque":"Lombaires"}],"consigne_cle":"Côtes rentrées","progression":"Reste à cette étape.","reperes":[{"repere":"Alignement","observe":"angle épaule ≈ 165°","cible":"180°","ok":False},{"repere":"Bras verrouillés","observe":"oui","cible":"tendus","ok":True}],"images_en_position":[3,4,5,6,7,8,9]}
async def claude(route):
    b=json.loads(route.request.post_data); name=b['tools'][0]['name']
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":name,"input":FIG}],"stop_reason":"tool_use"}))
async def meteo(route):
    hrs=[f"2026-10-18T{h:02d}:00" for h in range(24)]
    T=[24+8*max(0,1-abs(h-15)/8) for h in range(24)]; Td=[22]*24
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"current":{"temperature_2m":31,"relative_humidity_2m":70,"dew_point_2m":25},"hourly":{"time":hrs,"temperature_2m":T,"dew_point_2m":Td}}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.anthropic.com/**',claude); await A.route('https://api.open-meteo.com/**',meteo)
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();setKey('sk-ant-A');save();setMod('muscu','figures')"); await A.wait_for_timeout(400)
    # placement test
    await A.evaluate("skTestOpen('pushup')"); await A.wait_for_timeout(100); await A.screenshot(path='g_test.png')
    await A.evaluate("skTestAns(1);skTestAns(1);skTestAns(1);skTestAns(0)"); print('placement st', await A.evaluate("skS('pushup').st"))
    # quality
    await A.evaluate("skLogOpen('pushup');SKL.q=5;"); await A.screenshot(path='g_log.png')
    await A.evaluate("skLogSave()"); print('q5 ok count', await A.evaluate("skOk(SKID('pushup'),3)"))
    await A.evaluate("skS('pushup').log.forEach(l=>l.d='2026-10-10');skLogOpen('pushup');SKL.q=8;skLogSave();skLogOpen('pushup');SKL.q=8;skS('pushup').log.forEach(l=>{});"); 
    await A.evaluate("skS('pushup').log[skS('pushup').log.length-1].d='2026-10-12';save();skLogOpen('pushup');SKL.q=8;skLogSave()"); print('after 2 good st', await A.evaluate("skS('pushup').st"))
    # equipment
    await A.evaluate("S.mp={...MP(),equip:{...MP().equip,rings:true,para:true}};save();renderAll()"); print('locked w/ rings', await A.evaluate("SK.filter(skLocked).length"), 'eqnote', await A.evaluate("skEqNote(SKID('lsit'))"))
    # deload
    print('deload', await A.evaluate("[weekIdx(),skDeload()]"))
    await A.evaluate("skPin('hs');skPin('pushup')"); print('fig', await A.evaluate("figObj().t"))
    await A.evaluate("setMod('muscu','figures')"); await A.wait_for_timeout(200); await A.screenshot(path='g_fig.png',full_page=True)
    # video figure analysis with synthetic frames
    await A.evaluate("""(async()=>{const c=document.createElement('canvas');c.width=60;c.height=80;const x=c.getContext('2d');x.fillStyle='#8a6';x.fillRect(0,0,60,80);const src=c.toDataURL('image/jpeg');openTech('sk_hs_3');TX.frames=Array.from({length:12},(_,i)=>({t:+(i*2.5).toFixed(1),src}));S.mediaConsent=1;await analyzeTech();})()""")
    await A.wait_for_timeout(1500); print('tech', await A.evaluate("JSON.stringify({hold:TX.res.hold,rep:TX.res.rep.length,pos:TX.res.pos})"))
    await A.screenshot(path='g_tech.png',full_page=True)
    print('clips', await A.evaluate("CL.all().then(a=>a.map(c=>c.sk+':'+c.st+':'+c.src.length))"))
    await A.evaluate("skAlbum('hs')"); await A.wait_for_timeout(300); await A.screenshot(path='g_album.png')
    # heat
    await A.evaluate("closeSettings();heatLoad(13.75,100.5)"); await A.wait_for_timeout(500)
    print('heat', await A.evaluate("JSON.stringify({p:heatNow().pct,best:S.heat.best})"))
    print('today run', await A.evaluate("JSON.stringify(runPlan(weekIdx()).s.map(s=>[s.day,s.s]))"), 'dayIdx', await A.evaluate("dayIdx()"))
    await A.evaluate("setMod('trail','trail')"); await A.wait_for_timeout(300); await A.screenshot(path='g_heat.png',full_page=True)
    # race heat
    print('race', await A.evaluate("(()=>{const r={name:'X',date:'2026-12-06',km:30,dp:1800,goal:null,aid:[]};const a=raceStrategy(r).T;r.temp=30;r.hum=70;const b=raceStrategy(r);return fmtH(a)+' -> '+fmtH(b.T)+' heat '+b.heat.toFixed(3)})()"))
    # HRR synthetic
    print('hrr', await A.evaluate("""JSON.stringify(hrrOf((()=>{const t=[],hr=[];for(let i=0;i<400;i++){t.push(i*9);const ph=(i*9)%300;hr.push(ph<120?130+ph/3:170-(ph-120)*0.4);}return {t,hr};})()))"""))
    await A.evaluate("""(()=>{const r=S.activities[0];curAct=r;const t=[],hr=[];for(let i=0;i<400;i++){t.push(i*9);const ph=(i*9)%300;hr.push(Math.round(ph<120?130+ph/3:Math.max(125,170-(ph-120)*0.4)));}const det={...demoDetail(r),t,hr,d:t.map(x=>x*3),alt:t.map(x=>1000+Math.sin(x/500)*50)};det.ll=null;renderAct(r,det);})()""")
    print('hrr stored', await A.evaluate("JSON.stringify(S.hrr)"))
    S2=await A.evaluate("document.querySelector('#actBody').innerText.includes('Récupération cardiaque')"); print('act card',S2)
    await A.evaluate("S.hrr[1]={d:'2026-09-01',v:18,n:3};S.hrr[2]={d:'2026-09-10',v:21,n:4};renderAll();setMod('trail','analyse')"); await A.wait_for_timeout(300)
    print('trend', await A.evaluate("document.querySelector('[data-page=analyse]').innerText.includes('5 dernières')"))
    # muscle map
    await A.evaluate("closeAct&&closeAct();S.done['s'+weekIdx()+'A']=true;setMod('muscu','suivi')"); await A.wait_for_timeout(300)
    print('muscles', await A.evaluate("JSON.stringify(Object.fromEntries(Object.entries(muscleWeek()).map(([k,v])=>[k,Math.round(v*10)/10])))"))
    await A.screenshot(path='g_suivi.png')
    # share fallback (headless: canShare false)
    await A.evaluate("shareSkill('pushup')"); await A.wait_for_timeout(800); await A.screenshot(path='g_share.png')
    src=await A.evaluate("document.querySelector('#sheetBody img')&&document.querySelector('#sheetBody img').src")
    print('share img', bool(src))
    if src:
      b=await A.evaluate("fetch(document.querySelector('#sheetBody img').src).then(r=>r.arrayBuffer()).then(b=>{let s='';new Uint8Array(b).forEach(x=>s+=String.fromCharCode(x));return btoa(s)})")
      open('g_card.png','wb').write(base64.b64decode(b))
    await A.evaluate("curAct=S.activities.find(a=>a.poly);actDet=null;shareAct()"); await A.wait_for_timeout(800)
    b=await A.evaluate("fetch(document.querySelector('#sheetBody img').src).then(r=>r.arrayBuffer()).then(b=>{let s='';new Uint8Array(b).forEach(x=>s+=String.fromCharCode(x));return btoa(s)})")
    open('g_card2.png','wb').write(base64.b64decode(b))
    print('ctx keys', await A.evaluate("JSON.stringify({c:coachContext().chaleur_du_jour,m:coachContext().muscles_7_jours,h:coachContext().recuperation_cardiaque_60s.length})"))
    await A.evaluate("openRace()"); await A.wait_for_timeout(100); print('race fields', await A.evaluate("!!document.querySelector('#r_temp')"))
    for t in ['muscu','renfo','figures','defis','suivi','chrono']:
        await A.evaluate(f"closeSettings();setMod('muscu','{t}')"); await A.wait_for_timeout(100)
    for t in ['trail','histo','analyse','plan']:
        await A.evaluate(f"setMod('trail','{t}')"); await A.wait_for_timeout(100)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
