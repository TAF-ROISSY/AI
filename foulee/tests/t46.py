"""v9.4 : retour en arrière (historique : raccourci → page → « ‹ Aujourd’hui », bouton retour du navigateur, fiches fermées par le retour, ✕ qui nettoie l’historique) et animation de démarrage de 2 s."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(1200)
    print('splash 1.2s', await A.evaluate("!!document.getElementById('splash')&&!$('#splash').classList.contains('out')"))
    await A.wait_for_timeout(900); print('splash 2.6s gone', await A.evaluate("!document.getElementById('splash')||$('#splash').classList.contains('out')"))
    await A.wait_for_timeout(400)
    await A.evaluate("loadDemo();renderAll();showTab('today')"); await A.wait_for_timeout(200)
    await A.locator('[data-page=today] .pin:has-text("Chrono")').click(); await A.wait_for_timeout(200)
    print('chrono', await A.evaluate("document.body.dataset.tab"), 'back btn', await A.evaluate("$('#modSeg').innerText"))
    await A.locator('#modSeg button[data-back]').click(); await A.wait_for_timeout(300); print('after back', await A.evaluate("document.body.dataset.tab"))
    await A.locator('#tabs button[data-sec=plan]').click(); await A.wait_for_timeout(100); await A.locator('#tabs button[data-sec=analyse]').click(); await A.wait_for_timeout(100)
    await A.go_back(); await A.wait_for_timeout(250); print('browser back', await A.evaluate("document.body.dataset.tab"))
    await A.evaluate("openShoes()"); await A.wait_for_timeout(150); await A.go_back(); await A.wait_for_timeout(250)
    print('sheet closed by back', await A.evaluate("!$('#sheet').classList.contains('on')"), 'still', await A.evaluate("document.body.dataset.tab"))
    await A.evaluate("openShoes()"); await A.wait_for_timeout(150); await A.evaluate("closeSettings()"); await A.wait_for_timeout(300)
    print('x cleans', await A.evaluate("!(history.state&&history.state.sheet)"), await A.evaluate("document.body.dataset.tab"))
    await A.go_back(); await A.wait_for_timeout(250); print('back again', await A.evaluate("document.body.dataset.tab"))
    await A.screenshot(path='v94.png')
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
