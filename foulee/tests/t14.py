import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
TECH={"exercice_visible":True,"qualite_video":"ok","note":8,"resume":"Bon alignement.","points_ok":["Gainage"],"corrections":[],"consigne_cle":"Pousse dans le sol","progression":"Passe à la suite."}
async def claude(route):
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":"analyse_technique","input":TECH}],"stop_reason":"tool_use"}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.anthropic.com/**',claude)
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();setKey('sk-ant-A');save();setMod('muscu','figures')"); await A.wait_for_timeout(400)
    print('tabs', await A.evaluate("[...document.querySelectorAll('.tabbar button, nav button')].map(b=>b.innerText.trim()).filter(x=>x).join('|')"))
    print('cards', await A.evaluate("document.querySelectorAll('[data-page=figures] .skc').length"), 'locked', await A.evaluate("document.querySelectorAll('[data-page=figures] .skc.lock').length"))
    await A.screenshot(path='f_list.png',full_page=True)
    # log 2 days successful on pushup step 0
    await A.evaluate("skLogOpen('pushup')"); await A.wait_for_timeout(200); await A.screenshot(path='f_log.png')
    await A.evaluate("skLogSave()"); r1=await A.evaluate("skS('pushup').st")
    await A.evaluate("skS('pushup').log[0].d='2026-10-15';save();skLogOpen('pushup');SKL.v=[12,12,12];skLogSave()"); r2=await A.evaluate("skS('pushup').st")
    print('pushup st after 1 day',r1,'after 2 days',r2)
    # failed log
    await A.evaluate("skLogOpen('pushup');SKL.v=[12,9,8];skLogSave()"); print('fail keeps', await A.evaluate("skS('pushup').st"))
    # pins
    await A.evaluate("skPin('pushup');skPin('pistol');skPin('hs');skPin('lsit')"); print('pins', await A.evaluate("SK.filter(k=>skS(k.id).pin).map(k=>k.id).join(',')"))
    fo=await A.evaluate("JSON.stringify(figObj()&&{t:figObj().t,r:figObj().timer.rounds})"); print('figObj',fo)
    await A.evaluate("setMod('muscu','renfo')"); await A.wait_for_timeout(300)
    print('bloc in séances', await A.evaluate("document.querySelector('[data-page=renfo]').innerText.includes('Bloc figures')"))
    # bar unlock
    await A.evaluate("S.mp={...MP(),equip:{...MP().equip,bar:true}};save();renderAll()"); print('locked after bar', await A.evaluate("SK.filter(skLocked).length"))
    # video validation
    await A.evaluate("S.mediaConsent=1;TX={ex:'sk_hs_0',frames:['data:image/jpeg;base64,AAAA','data:image/jpeg;base64,AAAA']}")
    has=await A.evaluate("typeof TX")
    print('TX',has)
    # simulate via skVideoOk after 1 log day
    await A.evaluate("skLogOpen('hs');skLogSave();skVideoOk('sk_hs_0')"); print('hs st', await A.evaluate("skS('hs').st"))
    print('ctx', await A.evaluate("JSON.stringify(coachContext().callisthenie)")[:300] if False else (await A.evaluate("JSON.stringify(coachContext().callisthenie)"))[:300])
    print('badges', await A.evaluate("badges(muscuStats()).filter(b=>/Funambule|Acrobate/.test(b[1])).map(b=>b[1]+':'+b[3]).join(',')"))
    await A.evaluate("setMod('muscu','figures')"); await A.wait_for_timeout(300); await A.screenshot(path='f_list2.png')
    await A.evaluate("openTech('sk_pushup_1')"); await A.wait_for_timeout(300); await A.screenshot(path='f_tech.png')
    for t in ['muscu','renfo','defis','suivi','chrono']:
        await A.evaluate(f"setMod('muscu','{t}')"); await A.wait_for_timeout(150)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
