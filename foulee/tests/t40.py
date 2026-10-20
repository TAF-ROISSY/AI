"""v8.8 : Apple Santé par raccourci (analyse du texte, presse-papiers, lien #sante=, VFC vs normale → forme, sommeil et FC repos reportés) ; mobilité guidée (routines, recommandation selon douleur / séance dure, chrono avec voix)."""
import os, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time, base64
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,permissions=['clipboard-read','clipboard-write'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    for t in ['FOULEE{"hrv":52.4,"rhr":49,"sleep":7.3,"d":"2026-10-20"}','FOULEE{"hrv":"45,6","rhr":"51 bpm","sleep":"6 h 45 min"}',"hrv=60;rhr=48;sleep=440",'{"vfc":38,"fc":55}','nimporte quoi']:
        print('parse', await A.evaluate("(t)=>JSON.stringify(healthParse(t))",t))
    # normale sur 10 jours puis jour bas
    await A.evaluate("S.health={};for(let i=1;i<=10;i++){const d=new Date();d.setDate(d.getDate()-i);S.health[iso(d)]={hrv:60+(i%3)*3,rhr:48,sleep:7.5};}save()")
    await A.evaluate("navigator.clipboard.writeText('FOULEE{\"hrv\":41,\"rhr\":55,\"sleep\":5.6}')")
    sc0=await A.evaluate("readiness().sc"); await A.evaluate("healthPaste()"); await A.wait_for_timeout(300)
    print('saved', await A.evaluate("JSON.stringify(S.health[iso(new Date())])"), 'sleep', await A.evaluate("JSON.stringify(S.sleep[iso(new Date())])"), 'check fc', await A.evaluate("S.check[iso(new Date())].fc"))
    print('effect', await A.evaluate("JSON.stringify(hrvEffect())"), 'sc', sc0, '→', await A.evaluate("readiness().sc"), await A.evaluate("readiness().why.filter(x=>/VFC|nuit|FC/.test(x)).join(' | ')"))
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(150); print('today card', await A.evaluate("$('[data-page=today]').innerText.includes('Apple Santé')"))
    await A.evaluate("showTab('forme')"); await A.wait_for_timeout(150); print('forme chart', await A.evaluate("document.querySelectorAll('[data-page=forme] circle[data-tip*=\" ms\"]').length"))
    await A.locator('[data-page=forme] .card:has-text("Apple Santé")').screenshot(path='s_health.png')
    await A.evaluate("openHealthHelp()"); print('help', await A.evaluate("$('#sheetBody').innerText.includes('Rechercher des échantillons de santé')")); await A.screenshot(path='s_help.png',full_page=True); await A.evaluate("closeSettings()")
    # lien #sante= (base64url)
    b=base64.urlsafe_b64encode(b'{"hrv":70,"rhr":46,"sleep":8,"d":"2026-10-18"}').decode().rstrip('=')
    await A.evaluate(f"location.hash='sante={b}'"); await A.wait_for_timeout(300)
    print('hash', await A.evaluate("JSON.stringify(S.health['2026-10-18'])"), await A.evaluate("location.hash===''"), 'synced', await A.evaluate("'health' in syncPayload().data"))
    # mobilité
    print('routines', await A.evaluate("MOBS.map(id=>PREV[id].title+':'+PREV[id].items.every(i=>CUE[i.id])).join(' | ')"))
    print('reco pain', await A.evaluate("S.check[iso(new Date())].pain=[{z:'achille',lv:2}];mobReco().id"), 'reco hips', await A.evaluate("S.check[iso(new Date())].pain=[{z:'hanche',lv:1}];mobReco().id"))
    print('reco hard', await A.evaluate("S.check[iso(new Date())].pain=[];const k=daySessions(weekIdx(),dayIdx(),'run')[0];k?(S.done[k.k]=/[ql]$/.test(k.k),(mobReco()||{}).id):'no run today'"))
    o=await A.evaluate("JSON.stringify((()=>{const o=prevObj('mob_post');return [o.t,o.timer.rounds,o.timer.ex.length,!!o.x]})())"); print('obj', o)
    await A.evaluate("openMob()"); print('sheet', await A.evaluate("document.querySelectorAll('#sheetBody .run').length")); await A.evaluate("closeSettings();mobStart('mob_hips')"); await A.wait_for_timeout(200)
    print('timer', await A.evaluate("document.body.dataset.tab"), await A.evaluate("JSON.stringify({w:CH.work||null,r:CH.rounds||null})"))
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(150); await A.screenshot(path='s_today.png',full_page=True)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
