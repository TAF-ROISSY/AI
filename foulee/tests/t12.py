import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json
from playwright.async_api import async_playwright
AN={"qualite_photos":"Bonne lumière, cadrage correct.","resume":"Posture globalement équilibrée, légère antéversion du bassin.","posture":[{"zone":"Bassin","constat":"légère bascule vers l’avant","impact":"peut charger le bas du dos en descente"}],"points_forts":["Jambes bien développées"],"priorites":[{"zone":"fessiers","pourquoi":"stabiliser le bassin en trail","exercices":["bridge","swing","inconnu"]},{"zone":"sangle abdominale","pourquoi":"gainage anti-extension","exercices":["deadbug","wheelk"]}],"evolution":"","message":"Bonne base, on cible le bassin."}
reqs=[]
async def claude(route):
    reqs.append(json.loads(route.request.post_data))
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":"analyse_corporelle","input":AN}],"stop_reason":"tool_use"}))
async def m():
    async with async_playwright() as p:
        br=await p.chromium.launch(args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
        ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,permissions=['camera'])
        pg=await ctx.new_page();e=[];pg.on('pageerror',lambda x:e.append(str(x)))
        await pg.route('https://fonts.**',lambda r: r.abort()); await pg.route('https://api.anthropic.com/**',claude)
        await pg.goto('http://127.0.0.1:8765/index.html'); await pg.evaluate("loadDemo();setKey('sk-ant-test');setMod('muscu','suivi')"); await pg.wait_for_timeout(500)
        await pg.screenshot(path='b_empty.png')
        await pg.evaluate("openCam()"); await pg.wait_for_timeout(1500)
        print('live',await pg.evaluate("CAM.live"))
        await pg.screenshot(path='b_cam.png')
        await pg.evaluate("CAM.timer=false")
        for i in range(3):
            await pg.click('.snap'); await pg.wait_for_timeout(400)
            await pg.click("#camBar button:nth-child(2)"); await pg.wait_for_timeout(400)
        await pg.wait_for_timeout(500)
        print('photos',await pg.evaluate("IDB.all().then(a=>a.length)"))
        await pg.evaluate("S.bodyConsent=1;IDB.all().then(a=>analyzeBody(a[0].id))"); await pg.wait_for_timeout(1500)
        await pg.evaluate("IDB.all().then(a=>applyFocus(a[0].id))"); await pg.wait_for_timeout(500)
        await pg.evaluate("setMod('muscu','suivi')"); await pg.wait_for_timeout(600)
        await pg.fill('#m_poids','79.2'); await pg.fill('#m_fat','19.5'); await pg.fill('#m_mus','60.1'); await pg.fill('#m_tour','88')
        await pg.evaluate("S.mesures.push({d:'2026-09-15',p:80.4,f:21.2,mu:59.8,t:90});addMes()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path='b_full.png',full_page=True)
        rq=reqs[0]; print('img blocks',sum(1 for c in rq['messages'][0]['content'] if c['type']=='image'),'focus',await pg.evaluate("JSON.stringify(S.focus)"),'nutri',await pg.evaluate("JSON.stringify(nutri())"))
        print(e); await br.close()
asyncio.run(m())
