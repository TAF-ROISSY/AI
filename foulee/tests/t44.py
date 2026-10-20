"""v9.2 : page Plus repensée (icônes SVG au trait dans des pastilles teintées, groupes, lignes iOS / colonnes iPad, pas d'emoji) et animation de démarrage (tracé de crête, disparition, mouvement réduit)."""
import os, re
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
EMO=re.compile('[\U0001F300-\U0001FAFF☀-➿]')
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch()
    for vw,nm in [((390,844),'ios'),((1180,820),'ipad')]:
      ctx=await br.new_context(viewport={'width':vw[0],'height':vw[1]},device_scale_factor=2)
      A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
      await A.route('https://fonts.**',lambda r:r.abort())
      await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(250)
      if nm=='ios':
        print('splash on', await A.evaluate("!!document.getElementById('splash')&&getComputedStyle($('#splash')).opacity"))
        await A.screenshot(path='sp_mid.png')
      await A.wait_for_timeout(2400); print(nm,'splash gone', await A.evaluate("!document.getElementById('splash')"))
      await A.evaluate("loadDemo();renderAll();showTab('plus')"); await A.wait_for_timeout(250)
      el='[data-page=plus]'
      print(nm,'rows', await A.evaluate(f"document.querySelectorAll('{el} .prow').length"), 'svg', await A.evaluate(f"document.querySelectorAll('{el} .pic svg path, {el} .pic svg circle, {el} .pic svg rect').length>40"), 'groups', await A.evaluate(f"[...document.querySelectorAll('{el} .pgrp h3')].map(h=>h.textContent).join('|')"))
      txt=await A.evaluate(f"$('{el}').innerText"); print(nm,'emoji', EMO.findall(txt))
      print(nm,'overflow', await A.evaluate("document.documentElement.scrollWidth>innerWidth"), 'cols', await A.evaluate(f"getComputedStyle($('{el} .plus')).columnCount"))
      await A.screenshot(path=f'plus_{nm}.png',full_page=True)
      await A.locator(f'{el} .prow:has-text("Chaussures")').click(); await A.wait_for_timeout(150); print(nm,'click', await A.evaluate("$('#sheetBody').innerText.includes('paire')||$('#sheetBody').innerText.length>20"))
      print('ERR',nm,errs); await ctx.close()
    ctx=await br.new_context(viewport={'width':390,'height':844},reduced_motion='reduce'); A=await ctx.new_page()
    await A.route('https://fonts.**',lambda r:r.abort()); await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(1100)
    print('reduced gone', await A.evaluate("!document.getElementById('splash')"))
    await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
