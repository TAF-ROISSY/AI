import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, io
from playwright.async_api import async_playwright
from PIL import Image
im=Image.new('RGB',(256,256),(210,214,200)); b=io.BytesIO(); im.save(b,'PNG'); TILE=b.getvalue()
D=AS+'/'
async def m():
    async with async_playwright() as p:
        br=await p.chromium.launch();pg=await br.new_page(viewport={'width':390,'height':844},device_scale_factor=2);e=[];pg.on('pageerror',lambda x:e.append(str(x)))
        await pg.route('https://fonts.**',lambda r: r.abort())
        await pg.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
        await pg.route('https://*.tile.opentopomap.org/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
        await pg.goto('file:///home/claude/foulee/index.html'); await pg.evaluate("loadDemo()")
        t=await pg.evaluate("(()=>{const t0=performance.now();RC=null;const c=routeClusters();return [performance.now()-t0,c.length,c.map(x=>x.runs.length+'×'+x.km.toFixed(1)).join(' ')]})()")
        print('clusters',t)
        await pg.evaluate("setMod('trail','histo')"); await pg.wait_for_timeout(400)
        await pg.screenshot(path='y_histo.png',full_page=True)
        await pg.evaluate("renderRoute(routeClusters()[0].id)"); await pg.wait_for_timeout(1200); await pg.screenshot(path='y_route.png',full_page=True)
        await pg.evaluate("(()=>{const c=routeClusters()[0];compareRuns(c.last.id,c.best.id)})()"); await pg.wait_for_timeout(800); await pg.screenshot(path='y_cmp.png',full_page=True)
        await pg.evaluate("openAct(routeClusters()[1].last.id)"); await pg.wait_for_timeout(800)
        print('act has cmp', await pg.evaluate("document.querySelector('#actBody').innerText.includes('Comparée à ce même parcours')"))
        print(e); await br.close()
asyncio.run(m())
