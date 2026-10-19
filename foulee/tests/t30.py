"""v7.6 : apparence — thèmes (crépuscule, nuit, clair, auto), palettes de couleurs, polices ; propre à l'appareil (localStorage foulee_look), appliquée avant l'affichage."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,color_scheme='light')
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    v=lambda n:A.evaluate(f"getComputedStyle(document.body).getPropertyValue('{n}').trim()")
    print('default', await A.evaluate("document.documentElement.dataset.th"), await v('--bg'), await v('--trail'))
    await A.evaluate("openSettings()"); await A.wait_for_timeout(100)
    print('card', await A.evaluate("$('#lookCard').querySelectorAll('.lk-opt').length"))
    await A.locator('#lookCard button:has-text("Clair")').click(); await A.wait_for_timeout(100)
    print('clair', await A.evaluate("document.documentElement.dataset.th"), await A.evaluate("getComputedStyle(document.body).backgroundColor"), await A.evaluate("getComputedStyle(document.body).color"), 'meta', await A.evaluate("document.querySelector('meta[name=theme-color]').content"))
    print('  still open', await A.evaluate("!!$('#lookCard .lk-opt.on')"), await A.evaluate("[...document.querySelectorAll('#lookCard .lk-opt.on')].map(b=>b.innerText.split('\\n')[0]).join('|')"))
    await A.screenshot(path='l_settings_clair.png')
    await A.evaluate("closeSettings()")
    for t in [['trail','trail'],['trail','plan'],['trail','courses'],['muscu','muscu'],['cross','cross']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(120); await A.screenshot(path=f'l_clair_{t[1]}.png')
    await A.evaluate("lookSet('pal','foret')"); print('foret', await v('--trail'), await v('--muscu'))
    await A.evaluate("lookSet('font','lisible')"); print('font', await A.evaluate("getComputedStyle(document.body).fontFamily.split(',')[0]"), await A.evaluate("document.getElementById('lookFont').href.includes('Atkinson')"))
    await A.evaluate("lookSet('th','nuit')"); print('nuit', await A.evaluate("getComputedStyle(document.body).backgroundColor"))
    await A.evaluate("setMod('trail','trail')"); await A.wait_for_timeout(100); await A.screenshot(path='l_nuit_foret.png')
    await A.evaluate("lookSet('th','auto')"); print('auto (light system)', await A.evaluate("document.documentElement.dataset.th"))
    # persistance + appliqué avant le rendu
    await A.reload(); th=await A.evaluate("document.documentElement.dataset.th+'/'+document.documentElement.dataset.pal+'/'+document.documentElement.dataset.font")
    print('reload', th, 'nosync', await A.evaluate("!JSON.stringify(syncPayload()).includes('foulee_look')&&!('look' in S.settings)"))
    early=await A.evaluate("(()=>{const sc=[...document.scripts].findIndex(x=>x.textContent.includes('function lookApply'));const st=[...document.head.children].findIndex(x=>x.tagName==='STYLE');return sc>=0&&document.scripts[sc].parentNode===document.head;})()")
    print('in head', early)
    await A.evaluate("lookReset()"); print('reset', await A.evaluate("document.documentElement.dataset.th"), await v('--trail'))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
