"""v11.4 : pages harmonisées — en-tête (sur-titre + titre) et carte à la une sur Plan (course, muscu, semaine), Courses, Sorties, Analyse, Forme, Progrès ; Commencer depuis le plan ; courses sans objectif sans doublon ; iPad."""
import asyncio
from playwright.async_api import async_playwright
async def setup(pg):
    await pg.add_init_script("navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};")
    for u in ['https://fonts.**','https://api.anthropic.com/**','https://cdnjs.cloudflare.com/**','https://*open-meteo.com/**']: await pg.route(u,lambda r:r.abort())
JS="(()=>{const el=$('[data-page=TT]'),h=el.querySelectorAll(':scope>.f-pghead');return h.length+' '+(h[0]?h[0].innerText.replace(/\\n/g,' / '):'')+' | hero '+(el.querySelector(':scope>.f-pghero .f-hero-t')||{}).textContent})()"
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    for nm,vw,vh in [('ios',390,844),('ipad',1180,820)]:
      ctx=await br.new_context(viewport={'width':vw,'height':vh}); A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append(nm+' '+str(x))); await setup(A)
      await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
      await A.evaluate("loadDemo();(()=>{const w=weekIdx(),d=dayIdx();daySessions(w,d).forEach(o=>{S.done[o.k]=false;if(S.links)delete S.links[o.k]});})();save();renderAll()"); await A.wait_for_timeout(200)
      for t in ['plan','renfo','sports','cross','courses','histo','analyse','forme','suivi']:
        await A.evaluate(f"showTab('{t}')"); await A.wait_for_timeout(120)
        r=await A.evaluate(JS.replace('TT',t))
        print(nm,t,r)
      await A.evaluate("renderAll();renderAll()"); print(nm,'no double', await A.evaluate("document.querySelectorAll('.f-pghead').length"))
      if nm=='ios':
        await A.evaluate("showTab('plan')"); k=await A.evaluate("($('[data-page=plan] .f-hero')||{dataset:{}}).dataset.k")
        b=A.locator('[data-page=plan] .f-pghero .f-go')
        if await b.count(): await b.click(); await A.wait_for_timeout(200); print('plan commencer',k,await A.evaluate("$('#grv').classList.contains('on')")); await A.evaluate("grClose()")
        else: print('plan commencer absent (pas de course aujourd’hui)',k)
        print('courses race cards', await A.evaluate("document.querySelectorAll('[data-page=courses] .card.race').length"))
        await A.evaluate("S.race={name:'Trail test',date:iso(new Date(Date.now()+20*864e5)),km:30,dp:1200};save();renderAll();showTab('courses')"); await A.wait_for_timeout(150)
        print('courses avec objectif', await A.evaluate("$('[data-page=courses] .f-pghero').innerText.replace(/\\n/g,' · ').slice(0,140)"), 'race cards', await A.evaluate("document.querySelectorAll('[data-page=courses] .card.race').length"))
        await A.screenshot(path='v114_courses.png')
      print(nm,'overflow', await A.evaluate("document.documentElement.scrollWidth>innerWidth"))
      await A.evaluate("showTab('plan')"); await A.wait_for_timeout(150); await A.screenshot(path=f'v114_{nm}_plan.png'); await ctx.close()
    print('ERR', errs); await br.close()
asyncio.run(m())
