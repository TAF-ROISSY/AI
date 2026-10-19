import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json
from playwright.async_api import async_playwright
reqs=[]
SEANCE={"titre":"Jambes de trailer, version douce","resume":"Ta sortie longue d'hier pèse encore : on garde le bas du corps léger et on charge le haut.","duree_min":30,"echauffement":"5 min de mobilité hanches et épaules.","blocs":[{"nom":"Bloc force","format":"series","exercices":[{"id":"push","prescription":"4 × 10","consigne":"Descente en 2 s"},{"id":"row","prescription":"4 × 12 /bras","consigne":"Coude vers la hanche"},{"id":"inconnu","prescription":"x","consigne":"x"}]},{"nom":"Finisher","format":"emom","exercices":[{"id":"hollow","prescription":"30 s","consigne":"Bas du dos plaqué"}]}],"chrono":{"mode":"interval","travail_s":45,"repos_s":75,"repetitions":8,"minutes":0},"retour_au_calme":"Étirements pectoraux et mollets."}
BILAN={"titre":"Semaine solide","resume":"24 km et 3 séances muscu.","points_forts":["Régularité"],"vigilance":["Zone grise 70 %"],"ajustements":[{"module":"trail","action":"Footings à 6:00/km"},{"module":"muscu","action":"Renfo A le mercredi"},{"module":"nutrition","action":"140 g de protéines"}],"message":"Continue !"}
async def handler(route):
    body=json.loads(route.request.post_data); reqs.append((route.request.headers, body))
    tools=[t['name'] for t in body.get('tools',[])]
    if 'creer_seance' in tools: content=[{"type":"text","text":"Voici ta séance."},{"type":"tool_use","id":"t1","name":"creer_seance","input":SEANCE}]
    elif 'bilan_semaine' in tools: content=[{"type":"tool_use","id":"t2","name":"bilan_semaine","input":BILAN}]
    else: content=[{"type":"thinking","thinking":"..."},{"type":"text","text":"Aujourd'hui : **footing facile** 40 min.\n- Allure 6:00/km\n- 6 lignes droites"}]
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":content,"stop_reason":"end_turn"}))
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2)
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.route('https://api.anthropic.com/**',handler)
        await pg.goto('file:///home/claude/foulee/index.html')
        await pg.evaluate('loadDemo()')
        await pg.evaluate("setKey('sk-ant-test')")
        await pg.click('button[aria-label=Coach]')
        await pg.click('#chatQ button')
        await pg.wait_for_timeout(500)
        await pg.screenshot(path='c_chat.png')
        await pg.click('button[aria-label=Fermer]')
        await pg.click('#modSeg button[data-mod=muscu]')
        await pg.evaluate('openGen()'); await pg.screenshot(path='c_gen.png')
        await pg.click('#genBtn'); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelectorAll('[data-page=muscu] details').forEach(d=>d.open=true)")
        await pg.screenshot(path='c_seance.png',full_page=True)
        print('custom',await pg.evaluate("CO().custom.length"), await pg.evaluate("JSON.stringify(CO().custom[0].s.timer)"))
        await pg.evaluate("toggleDone('c'+CO().custom[0].id)"); await pg.evaluate("saveMuscuFb()")
        print('stats',await pg.evaluate("muscuStats().done.length"))
        await pg.click('#modSeg button[data-mod=cross]')
        await pg.evaluate("genBilan()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path='c_bilan.png',full_page=True)
        # erreur 401
        await pg.unroute('https://api.anthropic.com/**')
        await pg.route('https://api.anthropic.com/**',lambda r: r.fulfill(status=401,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"error":{"message":"invalid x-api-key"}}'))
        await pg.evaluate("openCoach()"); await pg.evaluate("sendChat('test')"); await pg.wait_for_timeout(400)
        print('err msg', await pg.evaluate("CO().chat.slice(-1)[0].text"))
        h,bd=reqs[0]
        print('headers ok', h.get('x-api-key'), h.get('anthropic-version'), h.get('anthropic-dangerous-direct-browser-access'), bd['model'], bd['max_tokens'], len(bd['system']))
        print('tool strict', reqs[1][1]['tools'][0].get('strict'), 'lib has swing?', 'swing =' in reqs[1][1]['messages'][0]['content'])
        print('export has key?', 'sk-ant' in await pg.evaluate("JSON.stringify(S)"))
        print('ERR',errs)
        await b.close()
asyncio.run(main())
