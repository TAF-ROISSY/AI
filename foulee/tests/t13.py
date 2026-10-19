import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, re, subprocess, time
from playwright.async_api import async_playwright
GIST={}  # id -> {id, description, files:{name:{content}}}
calls=[]
async def gh(route):
    req=route.request; u=req.url; m=req.method; calls.append(m+' '+u.split('api.github.com')[1])
    if req.headers.get('authorization')!='Bearer ghp_test':
        return await route.fulfill(status=401,body='{}',headers={'access-control-allow-origin':'*'})
    def out(o,st=200): return route.fulfill(status=st,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps(o))
    def view(g): return {'id':g['id'],'description':g['description'],'files':{n:{'filename':n,'content':f['content'],'truncated':False,'raw_url':'x'} for n,f in g['files'].items()}}
    path=u.split('api.github.com')[1]
    if m=='GET' and path.startswith('/gists?'): return await out([{'id':g['id'],'description':g['description']} for g in GIST.values()])
    if m=='POST' and path=='/gists':
        b=json.loads(req.post_data); gid='g'+str(len(GIST)+1); GIST[gid]={'id':gid,'description':b['description'],'files':{n:{'content':f['content']} for n,f in b['files'].items()}}; return await out(view(GIST[gid]),201)
    mm=re.match(r'/gists/(\w+)$',path)
    if mm and mm.group(1) in GIST:
        g=GIST[mm.group(1)]
        if m=='GET': return await out(view(g))
        if m=='PATCH':
            for n,f in json.loads(req.post_data)['files'].items():
                if f is None: g['files'].pop(n,None)
                else: g['files'][n]={'content':f['content']}
            return await out(view(g))
    return await out({'message':'nf'},404)
TECH={"exercice_visible":True,"qualite_video":"Cadrage correct.","note":7,"resume":"Bonne charnière de hanche, dos un peu arrondi en bas.","points_ok":["Projection par les hanches"],"corrections":[{"image":3,"probleme":"Dos arrondi en bas du mouvement","correction":"Pousse les fesses en arrière, regard 2 m devant","risque":"Charge le bas du dos"}],"consigne_cle":"Hanches en arrière, dos long","progression":"Garde 12 kg tant que le dos n’est pas neutre."}
async def claude(route):
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":"analyse_technique","input":TECH}],"stop_reason":"tool_use"}))
async def page(br):
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda x:errs.append(str(x)))
    await pg.route('https://fonts.**',lambda r: r.abort()); await pg.route('https://api.github.com/**',gh); await pg.route('https://api.anthropic.com/**',claude)
    await pg.goto('http://127.0.0.1:8765/index.html'); return pg,errs
async def m():
    async with async_playwright() as p:
        br=await p.chromium.launch()
        A,ea=await page(br)
        await A.evaluate("loadDemo();setKey('sk-ant-A');S.settings.poids=81;S.mesures.push({d:'2026-10-01',p:81,t:90});S.done['s0A']=true;S.log=[{id:1,d:'2026-10-10',k:'s0A',ex:'goblet',sets:[{kg:12,r:12},{kg:12,r:12},{kg:12,r:12}]}];save();")
        await A.evaluate("IDB.put({id:111,d:'2026-10-01',front:'data:image/jpeg;base64,'+btoa('F'.repeat(3000)),side:'data:image/jpeg;base64,'+btoa('S'.repeat(3000)),back:null,an:null})")
        await A.evaluate("openSettings()"); await A.fill('#v_tok','ghp_test'); await A.fill('#v_pass','montagne bleue 42'); await A.evaluate("enableSync()"); await A.wait_for_timeout(4000)
        print('A sync', await A.evaluate("JSON.stringify({on:VC().on,err:VC().err,gist:VC().gist})"), 'files', sorted(GIST['g1']['files'].keys()) if GIST else None)
        vault=GIST['g1']['files']['foulee.vault']['content']; print('vault encrypted', 'goblet' not in vault and 'sk-ant' not in vault, len(vault))
        # appareil B : mauvaise phrase puis bonne
        B,eb=await page(br)
        await B.evaluate("setVC({token:'ghp_test',pass:'mauvaise phrase',on:true});syncNow(true)"); await B.wait_for_timeout(3500)
        print('B wrong pass', await B.evaluate("VC().err"), 'remote untouched', GIST['g1']['files']['foulee.vault']['content']==vault)
        await B.evaluate("setVC({pass:'montagne bleue 42',err:null,lastPushed:0});syncNow(true)"); await B.wait_for_timeout(4000)
        print('B got', await B.evaluate("JSON.stringify({poids:S.settings.poids,mes:S.mesures.length,done:S.done.s0A,log:(S.log||[]).length,key:getKey()})"), await B.evaluate("IDB.all().then(a=>a.map(x=>x.id+':'+(x.front||'').length))"))
        # B ajoute une mesure, supprime la mesure du 1er
        await B.evaluate("S.mesures.push({d:'2026-10-15',p:80,t:89});delMes('2026-10-01');syncNow(true)"); await B.wait_for_timeout(4000)
        await A.evaluate("syncNow(true)"); await A.wait_for_timeout(4000)
        print('A after B', await A.evaluate("JSON.stringify(S.mesures.map(m=>m.d))"))
        # carnet de charges : 2e séance
        await A.evaluate("setMod('muscu','renfo')"); await A.wait_for_timeout(300)
        k=await A.evaluate("Object.keys(LOGREG).find(k=>/^s\\d+A$/.test(k))")
        await A.evaluate(f"S.log=[{{id:1,d:'2026-10-10',k:'s99A',ex:'goblet',sets:[{{kg:12,r:12}},{{kg:12,r:12}},{{kg:12,r:12}}]}}];MP().equip.kb16=true;"); await A.evaluate(f"openLogFor('{k}')"); await A.wait_for_timeout(300); await A.screenshot(path='v_log.png')
        print('hint', await A.evaluate("document.querySelector('.hint')&&document.querySelector('.hint').innerText"))
        await A.evaluate("saveLog()"); print('log entries', await A.evaluate("S.log.length"))
        await A.evaluate("setMod('muscu','suivi')"); await A.wait_for_timeout(400); await A.screenshot(path='v_prog.png',full_page=True)
        # course
        gpx=open(os.path.join(AS,'test_race.gpx')).read()
        r=await A.evaluate("t=>{const g=parseGpx(t),st=gpxStats(g.pts);S.race={name:g.name,date:'2026-12-06',km:+st.km.toFixed(1),dp:st.up,goal:null,aid:[10,20],gpx:g};save();const R=raceStrategy(S.race);const sum=R.km.reduce((a,k)=>a+k.t,0);S.race.goal=4*3600;const R2=raceStrategy(S.race);S.race.goal=null;return JSON.stringify({km:st.km.toFixed(2),up:st.up,T:fmtH(R.T),sumOK:Math.abs(sum-R.T)<2,key:R.key.length,aid:R.aid.map(a=>fmtH(a.cum)),goal:fmtH(R2.T),flat:fmtPace(R.flat)})}",gpx)
        print('race',r)
        await A.evaluate("setMod('trail','plan')"); await A.wait_for_timeout(300); await A.screenshot(path='v_plan.png')
        await A.evaluate("openStrategy()"); await A.wait_for_timeout(600); await A.screenshot(path='v_strat.png',full_page=True)
        await A.evaluate("closeAct();setMod('trail','trail')"); await A.wait_for_timeout(300); await A.screenshot(path='v_thome.png')
        # vidéo
        await A.evaluate("openTech('swing')"); await A.wait_for_timeout(300)
        await A.set_input_files('#sheetBody input[type=file]',os.path.join(AS,'foulee_test_vid.webm')); await A.wait_for_timeout(6000)
        print('frames', await A.evaluate("TX.frames&&TX.frames.length"), await A.evaluate("TX.err"))
        await A.evaluate("S.mediaConsent=1;analyzeTech()"); await A.wait_for_timeout(1500)
        await A.screenshot(path='v_tech.png',full_page=True)
        print('tech', await A.evaluate("JSON.stringify((S.tech||[]).map(x=>x.ex+' '+x.an.note))"))
        print('ctx', await A.evaluate("Object.keys(coachContext()).join(',')"), await A.evaluate("JSON.stringify(coachContext().objectif_course)"))
        print('ERR A',ea,'ERR B',eb)
        await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
