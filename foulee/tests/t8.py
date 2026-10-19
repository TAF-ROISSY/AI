import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, base64, os
from playwright.async_api import async_playwright
D=AS+'/'
# tuile : dégradé simple pour visualiser
from PIL import Image; import io
im=Image.new('RGB',(256,256),(210,214,200)); b=io.BytesIO(); im.save(b,'PNG'); TILE=b.getvalue()
def sess(t,km,d,ch=None): return {"actif":True,"titre":t,"distance_km":km,"denivele_m":d,"details":"Échauffement 15 min à 6:10/km puis corps de séance.","chrono":ch or {"mode":"aucun","travail_s":0,"repos_s":0,"repetitions":0}}
PROG={"resume":"Tu cours régulièrement mais trop souvent en zone grise.","constats":["24 km/sem en moyenne","3 semaines sans course"],"objectifs":["10 km sous 44:00"],
 "semaines":[{"numero":i+1,"theme":f"Base {i+1}","allegee":i%4==3,"qualite":sess("Côtes 10 × 45 s",9,180,{"mode":"interval","travail_s":45,"repos_s":90,"repetitions":10}),"facile":sess("Footing facile",8,40),"recup":{"actif":False,"titre":"","distance_km":0,"denivele_m":0,"details":"","chrono":{"mode":"aucun","travail_s":0,"repos_s":0,"repetitions":0}},"longue":sess("Sortie longue trail",14+i,400)} for i in range(12)]}
async def claude(route):
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({"content":[{"type":"tool_use","id":"t","name":"programme_trail","input":PROG}],"stop_reason":"tool_use"}))
async def m():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2);e=[];pg.on('pageerror',lambda x:e.append(str(x)))
        await pg.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
        await pg.route('https://*.tile.opentopomap.org/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
        await pg.route('https://*.basemaps.cartocdn.com/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
        await pg.route('https://fonts.**',lambda r: r.abort())
        await pg.route('https://api.anthropic.com/**',claude)
        await pg.goto('file:///home/claude/foulee/index.html'); await pg.evaluate("loadDemo()")
        await pg.evaluate("setMod('trail','histo')"); await pg.wait_for_timeout(300)
        await pg.screenshot(path='h_histo.png',full_page=True)
        await pg.click('.cal .dc.has'); await pg.wait_for_timeout(1500)
        box=await pg.query_selector('#profSvg'); await box.scroll_into_view_if_needed(); await pg.wait_for_timeout(200); bb=await box.bounding_box()
        await pg.mouse.move(bb['x']+bb['width']*0.55,bb['y']+bb['height']/2); await pg.wait_for_timeout(300)
        await pg.screenshot(path='h_act2.png')
        print('readout',await pg.inner_text('#actRead'))
        await pg.evaluate("closeAct();setKey('sk-ant-test');setMod('trail','plan')")
        await pg.evaluate("genProgramme()"); await pg.wait_for_timeout(800)
        await pg.screenshot(path='h_prog.png')
        await pg.evaluate("adoptProg()"); await pg.wait_for_timeout(300)
        print('plan', await pg.evaluate("runPlan(weekIdx()).s.map(x=>x.t+' '+x.s).join(' | ')"))
        await pg.screenshot(path='h_plan.png',full_page=True)
        print(e); await b.close()
asyncio.run(m())
