import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio
from playwright.async_api import async_playwright
R='fedb/repo/'
async def m():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2);e=[];pg.on('pageerror',lambda x:e.append(str(x)))
        await pg.route('https://fonts.**',lambda r: r.abort())
        hits=[]
        async def img(route):
            hits.append(route.request.url)
            await route.continue_()
        await pg.route('https://raw.githubusercontent.com/**',img)
        await pg.goto('file:///home/claude/foulee/index.html'); await pg.evaluate("loadDemo()")
        await pg.evaluate("startDefi('athena',0)"); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='x_defi.png')
        ok=await pg.evaluate("[...document.querySelectorAll('#chMedia img')].map(i=>i.naturalWidth)")
        print('img widths',ok[:4],'requests',len(hits))
        await pg.evaluate("setMod('muscu','renfo')"); await pg.click("[data-page=renfo] .sess.str >> text=Lancer le chrono >> nth=0"); await pg.wait_for_timeout(1500)
        print('exList',await pg.evaluate("CH.exList"))
        await pg.evaluate("openEx('burpee')"); await pg.wait_for_timeout(300); await pg.screenshot(path='x_burpee.png')
        print(e); await b.close()
asyncio.run(m())
