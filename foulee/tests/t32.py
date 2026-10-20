"""v8.0 : navigation en 5 sections (Aujourd’hui, Plan, Courses, Analyse, Plus) avec sous-sections, page Aujourd’hui trail + muscu, page Plus, compatibilité setMod/showTab, mise en page iPad / Mac (barre latérale, colonnes)."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def run(br,vw,vh,tag):
    ctx=await br.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2 if vw<600 else 1)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(200)
    print(tag,'boot', await A.evaluate("document.body.dataset.tab+'/'+document.body.dataset.sec"), 'tabs', await A.evaluate("[...document.querySelectorAll('#tabs button')].map(b=>b.textContent.trim()).join('|')"))
    await A.evaluate("loadDemo();renderAll();showTab('today')"); await A.wait_for_timeout(200)
    print(tag,'today', await A.evaluate("$('[data-page=today]').innerText.includes('Au programme')"), 'cdj', await A.evaluate("!!$('[data-page=today] details.cdj')"), 'dots', await A.evaluate("document.querySelectorAll('[data-page=today] .dot').length"), 'subnav hidden', await A.evaluate("$('#modSeg').hidden"))
    await A.screenshot(path=f'v8_{tag}_today.png')
    await A.locator('#tabs button[data-sec=plan]').click(); await A.wait_for_timeout(100)
    print(tag,'plan', await A.evaluate("document.body.dataset.tab"), 'sub', await A.evaluate("[...document.querySelectorAll('#modSeg button')].map(b=>b.textContent+(b.classList.contains('on')?'*':'')).join('|')"), 'title', await A.evaluate("$('#modSub').textContent"))
    await A.locator('#modSeg button[data-tab=renfo]').click(); await A.wait_for_timeout(100)
    print(tag,'renfo', await A.evaluate("document.body.dataset.tab+' mod='+document.body.dataset.mod"))
    await A.screenshot(path=f'v8_{tag}_renfo.png')
    await A.locator('#tabs button[data-sec=analyse]').click(); await A.locator('#modSeg button[data-tab=forme]').click(); await A.wait_for_timeout(100)
    await A.locator('#tabs button[data-sec=plan]').click(); print(tag,'remember', await A.evaluate("document.body.dataset.tab"))
    await A.locator('#tabs button[data-sec=analyse]').click(); print(tag,'remember2', await A.evaluate("document.body.dataset.tab"))
    await A.screenshot(path=f'v8_{tag}_forme.png')
    await A.locator('#tabs button[data-sec=plus]').click(); await A.wait_for_timeout(100)
    print(tag,'plus tiles', await A.evaluate("document.querySelectorAll('[data-page=plus] .prow').length"))
    await A.screenshot(path=f'v8_{tag}_plus.png')
    await A.locator('[data-page=plus] .prow:has-text("Intervalles")').click(); print(tag,'chrono', await A.evaluate("document.body.dataset.tab+'/'+document.body.dataset.sec"))
    # compat
    await A.evaluate("setMod('muscu')"); print(tag,'setMod muscu', await A.evaluate("document.body.dataset.tab"))
    await A.evaluate("setMod('trail','courses')"); print(tag,'setMod courses', await A.evaluate("document.body.dataset.tab+'/'+document.body.dataset.sec"))
    await A.evaluate("showTab('nope')"); print(tag,'unknown', await A.evaluate("document.body.dataset.tab"))
    await A.evaluate("showTab('histo')"); await A.reload(); await A.wait_for_timeout(200); print(tag,'restore', await A.evaluate("document.body.dataset.tab"))
    if vw>=1024:
        print(tag,'sidebar', await A.evaluate("getComputedStyle($('#tabs')).flexDirection+' w='+$('#tabs').getBoundingClientRect().width"), 'main left', await A.evaluate("Math.round($('main').getBoundingClientRect().left)"))
        await A.evaluate("showTab('today')"); print(tag,'columns', await A.evaluate("getComputedStyle($('[data-page=today]')).columnCount"))
        await A.evaluate("openSettings()"); await A.wait_for_timeout(100); await A.screenshot(path=f'v8_{tag}_settings.png'); await A.evaluate("closeSettings()")
        await A.evaluate("openCoach()"); await A.wait_for_timeout(150); print(tag,'coach drawer', await A.evaluate("Math.round($('#coach').getBoundingClientRect().width)")); await A.screenshot(path=f'v8_{tag}_coach.png'); await A.evaluate("closeCoach()")
    for t in ['today','plan','renfo','cross','courses','histo','analyse','forme','suivi','plus','figures','defis','chrono','trail','muscu']:
        await A.evaluate(f"showTab('{t}')"); await A.wait_for_timeout(40)
        ov=await A.evaluate("document.documentElement.scrollWidth>innerWidth+1")
        if ov: print(tag,'OVERFLOW',t)
    print(tag,'ERR',errs); await ctx.close()
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch()
    await run(br,390,844,'phone'); await run(br,1194,834,'ipad'); await run(br,1512,900,'mac')
    await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
