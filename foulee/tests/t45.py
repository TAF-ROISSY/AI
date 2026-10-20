"""v9.3 : emojis remplacés par des icônes SVG (observateur), raccourcis épinglés sur l'accueil, vibrations, confettis (semaine complète, records), mode montre en course guidée, invitation d'un proche (lien, code I:, bienvenue), icônes d'app et écrans de lancement iOS."""
import os, re, base64, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
EMO=re.compile('[\U0001F300-\U0001FAFF☀-⛿⭐⏱⏸]')
INIT="window.__vib=[];navigator.vibrate=(p)=>{window.__vib.push(p);return true};"
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,permissions=['clipboard-read','clipboard-write'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(1900)
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(300)
    for t in ['today','plan','renfo','courses','analyse','forme','trail','muscu','figures','defis','chrono','plus']:
        await A.evaluate(f"showTab('{t}')"); await A.wait_for_timeout(120)
        txt=await A.evaluate("$('main').innerText"); left=sorted(set(EMO.findall(txt)))
        print('emoji', t, len(left), ''.join(left), 'svg', await A.evaluate("document.querySelectorAll('main .ei').length"))
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(150)
    print('pins', await A.evaluate("[...document.querySelectorAll('[data-page=today] .pin span:last-child')].map(x=>x.textContent).join('|')"))
    await A.locator('[data-page=today] .pin').first.screenshot(path='v93_pin.png')
    await A.screenshot(path='v93_today.png')
    await A.evaluate("openPins()"); await A.locator('#sheetBody label.prow:has-text("Chaussures") input').click(); await A.wait_for_timeout(100)
    print('pin max', await A.evaluate("JSON.stringify(S.settings.pins)"))
    await A.locator('#sheetBody label.prow:has-text("Nutrition") input').click(); await A.locator('#sheetBody label.prow:has-text("Chaussures") input').click(); await A.wait_for_timeout(100)
    print('pins now', await A.evaluate("JSON.stringify(S.settings.pins)"), 'synced', await A.evaluate("'pins' in syncPayload().data.settings||JSON.stringify(syncPayload().data).includes('pins')"))
    await A.screenshot(path='v93_pinsheet.png',full_page=True); await A.evaluate("closeSettings()")
    # semaine complète → confettis + vibration
    await A.evaluate("window.__vib=[];(()=>{const w=weekIdx();const ks=[];for(let d=0;d<7;d++)daySessions(w,d).forEach(o=>{if(o&&o.k&&!o.cancel&&!o.race)ks.push(o.k)});ks.slice(0,-1).forEach(k=>S.done[k]=true);window.__last=ks[ks.length-1];S.done[window.__last]=false;save();})()")
    await A.evaluate("toggleDone(window.__last);closeSettings&&closeSettings()"); await A.wait_for_timeout(500)
    print('week done', await A.evaluate("weekDone(weekIdx())"), 'confetti', await A.evaluate("!!document.querySelector('canvas.confetti')"), 'vib', await A.evaluate("JSON.stringify(window.__vib)"))
    await A.screenshot(path='v93_confetti.png'); await A.wait_for_timeout(2800); print('confetti gone', await A.evaluate("!document.querySelector('canvas.confetti')"))
    # record VMA
    await A.evaluate("S.vma=[{id:'a',d:iso(new Date(Date.now()-864e5*20)),v:14}];save();vmaSave('cooper',3400,'gps')"); await A.wait_for_timeout(600); print('vma confetti', await A.evaluate("!!document.querySelector('canvas.confetti')"))
    # mode montre
    await A.evaluate("grOpen(daySessions(weekIdx(),dayIdx(),'run')[0]?daySessions(weekIdx(),dayIdx(),'run')[0].k:'vmatest');GR.on=true;GR.t0=Date.now();GR.dist=2350;grDraw()")
    await A.locator('#grBody button:has-text("Mode montre")').click(); await A.wait_for_timeout(150)
    print('mono', await A.evaluate("$('#grv').classList.contains('mono')"), await A.evaluate("!!$('#grBody .grm-p')"), await A.evaluate("getComputedStyle($('#grv')).backgroundColor"))
    await A.screenshot(path='v93_mono.png')
    await A.locator('#grBody button:has-text("Écran normal")').click(); print('normal', await A.evaluate("$('#grv').classList.contains('mono')"))
    await A.evaluate("GR.on=false;$('#grv').classList.remove('on')")
    # invitation
    await A.evaluate("S.settings.clientId='12345';S.settings.clientSecret='abcsecret';save();openInvite()"); await A.fill('#iv_n','Lucas')
    u=await A.evaluate("inviteUrl()"); print('invite url', u.split('#')[1][:20], 'has secret', 'abcsecret' in base64.urlsafe_b64decode(u.split('invite=')[1]+'==').decode())
    await A.locator('#iv_app').uncheck(); print('no app', 'cid' not in await A.evaluate("JSON.stringify(ivDec(inviteCode()))"))
    await A.screenshot(path='v93_invite.png',full_page=True)
    # nouvel appareil
    B=await (await br.new_context(viewport={'width':390,'height':844})).new_page(); B.on('pageerror',lambda x:errs.append('B '+str(x)))
    await B.route('https://fonts.**',lambda r:r.abort())
    await B.goto('http://127.0.0.1:8765/index.html#'+u.split('#')[1]); await B.wait_for_timeout(2200)
    print('B', await B.evaluate("JSON.stringify({cid:S.settings.clientId,sec:!!S.settings.clientSecret,tok:S.tokens,acts:S.activities.length,hash:location.hash})"), 'welcome', await B.evaluate("$('#sheetBody').innerText.includes('Bienvenue Lucas')"))
    await B.screenshot(path='v93_welcome.png',full_page=True)
    # code I: collé dans les réglages d'un autre appareil
    C=await (await br.new_context(viewport={'width':390,'height':844})).new_page(); await C.route('https://fonts.**',lambda r:r.abort())
    await C.goto('http://127.0.0.1:8765/index.html'); await C.wait_for_timeout(1900)
    await C.evaluate("openSettings()"); await C.evaluate("(v)=>{$('#s_link').value=v}",'I:'+u.split('invite=')[1]); await C.evaluate("linkStrava()"); await C.wait_for_timeout(200)
    print('C', await C.evaluate("S.settings.clientId"), await C.evaluate("$('#sheetBody').innerText.includes('Bienvenue')"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
