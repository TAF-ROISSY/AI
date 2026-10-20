"""v11 : refonte « La ligne de crête » — design system, Aujourd'hui en cockpit (séance du jour, 3 indicateurs, sections), Ton espace (recherche, cartes à la une, tuiles), iPad 2 colonnes ; + sommets autour de toi, photo du repas, négocier ma semaine, course entre amis."""
import os, json, time
import asyncio
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
async def setup(pg):
    await pg.add_init_script(INIT); await pg.route('https://fonts.**',lambda r:r.abort()); await pg.route('https://api.anthropic.com/**',lambda r:r.abort()); await pg.route('https://cdnjs.cloudflare.com/**',lambda r:r.abort()); await pg.route('https://*open-meteo.com/**',lambda r:r.abort()); await pg.route('https://overpass**',lambda r:r.abort())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2); A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append(str(x))); await setup(A)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();(()=>{const w=weekIdx(),d=dayIdx();daySessions(w,d).forEach(o=>{S.done[o.k]=false;if(S.links)delete S.links[o.k]});})();save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    T="[data-page=today]"
    print('version', await A.evaluate("APP_VER"), 'accent', await A.evaluate("getComputedStyle(document.body).getPropertyValue('--acc').trim()"), 'bg', await A.evaluate("getComputedStyle(document.body).backgroundColor"))
    print('head', await A.evaluate(f"$('{T} .f-hello').textContent"), 'ring', await A.evaluate(f"!!$('{T} .f-ring .gauge')"))
    print('hero', await A.evaluate(f"$('{T} .f-hero .f-hero-t').textContent"), '|', await A.evaluate(f"[...document.querySelectorAll('{T} .f-hero-m div')].map(x=>x.innerText.replace(/\\n/g,' ')).join(' · ')"))
    print('mets', await A.evaluate(f"[...document.querySelectorAll('{T} .f-met .f-eye')].map(x=>x.textContent).join('|')"))
    print('sections', await A.evaluate(f"[...document.querySelectorAll('{T} .f-sh h3')].map(x=>x.textContent).join('|')"))
    print('kept', await A.evaluate(f"['Au programme','Dernière'].map(t=>$('{T}').innerText.includes(t)).join(',')"), 'pins', await A.evaluate(f"document.querySelectorAll('{T} .pin').length"), 'xp', await A.evaluate(f"!!$('{T} .xp-mini')"), 'chk', await A.evaluate(f"document.querySelectorAll('{T} .sess .chk').length"))
    await A.screenshot(path='v110_today.png')
    k=await A.evaluate(f"$('{T} .f-hero').dataset.k")
    await A.locator(f'{T} .f-go').click(); await A.wait_for_timeout(250)
    print('commencer', k, await A.evaluate("$('#grv').classList.contains('on')||getComputedStyle($('#grv')).display!=='none'"))
    await A.evaluate("grClose&&grClose()"); await A.wait_for_timeout(100)
    await A.evaluate(f"(()=>{{const w=weekIdx(),d=dayIdx();daySessions(w,d).forEach(o=>S.done[o.k]=true);save();renderAll();}})()"); await A.wait_for_timeout(200)
    print('done hero', await A.evaluate(f"$('{T} .f-hero').className"), await A.evaluate(f"$('{T} .f-hero .f-hero-t').textContent"))
    # --- Ton espace
    await A.evaluate("showTab('plus')"); await A.wait_for_timeout(250); P="[data-page=plus]"
    print('space', await A.evaluate(f"$('{P} .f-hello').textContent"), 'rows', await A.evaluate(f"document.querySelectorAll('{P} .prow').length"), 'feat', await A.evaluate(f"[...document.querySelectorAll('{P} .prow.feat b')].map(x=>x.textContent).join('|')"))
    print('groups', await A.evaluate(f"[...document.querySelectorAll('{P} .pgrp h3')].map(x=>x.textContent).join('|')"))
    print('all reachable', await A.evaluate(f"PLUSI.filter(x=>!x.if||x.if()).every(x=>$('{P} .prow[data-k='+x.k+']'))"))
    await A.screenshot(path='v112_space.png',full_page=True)
    await A.fill(f'{P} .sp-q input','chaussu'); await A.wait_for_timeout(100)
    print('search', await A.evaluate(f"[...document.querySelectorAll('{P} .prow')].filter(r=>!r.hidden).map(r=>r.dataset.k).join(',')"), 'groups visibles', await A.evaluate(f"[...document.querySelectorAll('{P} .pgrp')].filter(g=>!g.hidden).length"))
    await A.fill(f'{P} .sp-q input','zzzz'); await A.wait_for_timeout(100); print('empty', await A.evaluate("!$('#spEmpty').hidden"))
    await A.fill(f'{P} .sp-q input',''); await A.wait_for_timeout(100)
    await A.locator(f'{P} .prow:has-text("Intervalles")').click(); await A.wait_for_timeout(150); print('tile click', await A.evaluate("document.body.dataset.tab"))
    # --- v10.4 : repas
    await A.evaluate("S.settings.poids=72;openMeal()"); await A.wait_for_timeout(150)
    print('meal', await A.evaluate("$('#sheetBody').innerText.slice(0,120).replace(/\\n/g,' / ')"), '| needs', (await A.evaluate("JSON.stringify(mealNeeds())"))[:160])
    await A.evaluate("closeSettings()")
    # --- négocier
    print('nego', await A.evaluate("(()=>{const D=negoDays().map(iso),av=[D[1],D[3],D[5]],R=negoLocal(av);const bad=R.decisions.filter(x=>x.action!=='annuler'&&!av.includes(x.jour)).length;return R.decisions.length+' décisions, hors dispo '+bad+' · '+R.resume})()"))
    print('nego apply', await A.evaluate("(()=>{const D=negoDays().map(iso);const n=negoApply(negoLocal([D[2],D[4],D[6]]));return n+' changement(s), mv '+Object.keys(S.mv||{}).length})()"))
    await A.evaluate("openNego()"); await A.wait_for_timeout(150); print('nego sheet', await A.evaluate("$('#sheetBody').innerText.includes('dispo')||$('#sheetBody').innerText.length>40")); await A.evaluate("closeSettings()")
    # --- course entre amis
    print('crew', await A.evaluate("(()=>{GR.dist=3000;GR.on=true;GR.crew=[{g:'a',n:'Lucas',d:{st:'run',upd:Date.now(),dist:3400,el:1200}},{g:'b',n:'Marie',d:{st:'run',upd:Date.now(),dist:2500,el:1200}}];const t=crewTxt(false);GR.on=false;GR.crew=null;return t})()"))
    # --- sommets
    print('peaks', await A.evaluate("(()=>{PK.me=[45.9,6.1];PK.alt=500;PK.list=[{n:'Mont Blanc',ele:4806,ll:[45.8326,6.8652]},{n:'Semnoz',ele:1699,ll:[45.79,6.1]}];return pkCompute().map(p=>p.n+' '+Math.round(p.b)+'° '+p.d.toFixed(1)+' km').join(' | ')})()"))
    try:
        await A.evaluate("openPeaks()"); await A.wait_for_timeout(400); print('peaks open', await A.evaluate("$('#pk').classList.contains('on')")); await A.evaluate("closePeaks()"); await A.wait_for_timeout(100); print('peaks closed', await A.evaluate("!$('#pk').classList.contains('on')"))
    except Exception as e: print('peaks ERR', e)
    print('overflow', await A.evaluate("document.documentElement.scrollWidth>innerWidth"))
    await ctx.close()
    # --- iPad
    ctx=await br.new_context(viewport={'width':1180,'height':820}); B=await ctx.new_page(); B.on('pageerror',lambda x:errs.append('B '+str(x))); await setup(B)
    await B.goto('http://127.0.0.1:8765/index.html'); await B.wait_for_timeout(2300); await B.evaluate("loadDemo();renderAll();showTab('today')"); await B.wait_for_timeout(300)
    print('ipad cols', await B.evaluate("getComputedStyle($('[data-page=today] .f-cols')).gridTemplateColumns"), 'nav pad', await B.evaluate("getComputedStyle($('#tabs')).paddingTop"))
    print('ipad overlap', await B.evaluate("(()=>{const b=[...document.querySelectorAll('#tabs button')].map(x=>x.getBoundingClientRect());return b[0].top>80})()"))
    await B.screenshot(path='v111_ipad.png'); await B.evaluate("showTab('plus')"); await B.wait_for_timeout(200); await B.screenshot(path='v112_ipad.png')
    print('ipad overflow', await B.evaluate("document.documentElement.scrollWidth>innerWidth"))
    print('ERR', errs); await br.close()
asyncio.run(m())
