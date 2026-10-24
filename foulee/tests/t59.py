"""v12.1 : intelligence foundation — splash Precision Pulse, check-up (stress, motivation), Bourse d'Énergie (calcul, carte, fiche, Pourquoi ?), mémoire Foulée (ajout, correction, hypothèse confirmée / réfutée, suppression + tombstone, export), coach (étiquettes Savoir / Déduire / Envisager, bloc <memoire>, propositions à valider, Pourquoi ?), Pourquoi ? du brief, Ton espace."""
import json, asyncio
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
BODIES=[]
REPLY=("[SAVOIR] Tu as couru 3 fois cette semaine.\n[DÉDUIRE] Ta charge monte plus vite que d’habitude.\n[ENVISAGER] Ton stress au travail pourrait expliquer la fatigue de jeudi.\n"
       "- Fais 40 min faciles demain.\n<memoire>[{\"type\":\"hypothesis\",\"ep\":\"envisaged\",\"c\":\"Les semaines chargées au travail ralentissent mes sorties\",\"conf\":0.4},"
       "{\"type\":\"semantic\",\"ep\":\"known\",\"c\":\"Préfère courir le matin\",\"conf\":0.9}]</memoire>")
async def api(route):
    BODIES.append(json.loads(route.request.post_data or '{}'))
    txt=REPLY if len(BODIES)==1 else "1. [SAVOIR] 3 sorties.\n2. Stress de vie chargé.\n3. [DÉDUIRE] Fatigue probable, confiance moyenne.\n4. Si tu dors bien ce soir, on garde la séance.\n5. Le repos protège la semaine."
    await route.fulfill(status=200,content_type='application/json',body=json.dumps({"content":[{"type":"text","text":txt}],"stop_reason":"end_turn"}))
async def setup(pg):
    await pg.add_init_script(INIT)
    for u in ['https://fonts.**','https://cdnjs.cloudflare.com/**','https://*open-meteo.com/**','https://overpass**','https://api.github.com/**','https://*.tile.**']:
        await pg.route(u,lambda r:r.abort())
    await pg.route('https://api.anthropic.com/**',api)
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2); A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append(str(x))); await setup(A)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(500)
    print('version', await A.evaluate("APP_VER"))
    print('splash 0.5s', await A.evaluate("!!document.getElementById('splash')&&!$('#splash').classList.contains('out')"), await A.evaluate("$('#splash .sp-sub').textContent"), await A.evaluate("$('#splash .sp-name span').textContent"), 'halo', await A.evaluate("!!$('#splash .sp-halo')"), 'stroke', await A.evaluate("getComputedStyle($('#splash .sp-ridge')).stroke.slice(0,12)"))
    await A.screenshot(path='v121_splash.png')
    await A.wait_for_timeout(1700); print('splash 2.2s gone', await A.evaluate("!document.getElementById('splash')"))
    R=await br.new_context(viewport={'width':390,'height':844},reduced_motion='reduce'); B=await R.new_page(); B.on('pageerror',lambda x:errs.append('B '+str(x))); await setup(B)
    await B.goto('http://127.0.0.1:8765/index.html'); await B.wait_for_timeout(1100); print('reduced gone', await B.evaluate("!document.getElementById('splash')")); await R.close()

    await A.evaluate("loadDemo();S.check={};S.mem=[];S.sleep={};save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    print('no checkup: energy', await A.evaluate("enData()"), 'card', await A.evaluate("!!$('[data-page=today] .en-card')"), 'banner', await A.evaluate("$('[data-page=today]').innerText.includes('Bourse d’Énergie')"))
    # --- check-up
    await A.evaluate("openCheck()"); await A.wait_for_timeout(150)
    print('check labels', await A.evaluate("[...document.querySelectorAll('#sheetBody .qlab')].map(x=>x.textContent.split(' (')[0].trim()).join('|')"))
    await A.locator('#sheetBody .chip', has_text='Sous pression').click(); await A.locator('#sheetBody .chip', has_text='Aucune').nth(1).click(); await A.locator('#sheetBody .chip', has_text='Épuisé').click()
    await A.evaluate("S.sleep[iso(new Date())]={h:5.5,q:2,t:Date.now()}")
    await A.locator('#sheetBody .btn', has_text='Enregistrer').click(); await A.wait_for_timeout(250)
    print('saved', await A.evaluate("JSON.stringify((({stress,motiv,mood})=>({stress,motiv,mood}))(S.check[iso(new Date())]))"))
    E=await A.evaluate("(()=>{const E=enData();return {sc:E.sc,lv:E.lv[1],dv:E.dv,ds:E.ds,n:E.P.length,txt:E.txt}})()"); print('energy', E)
    print('card', await A.evaluate("!!$('[data-page=today] .en-card')"), await A.evaluate("$('[data-page=today] .en-card .en-sc').textContent"), 'why btn', await A.evaluate("!!$('[data-page=today] .en-card .why-b')"))
    await A.evaluate("S.check[iso(new Date())].stress=0;S.check[iso(new Date())].mood=3;S.sleep[iso(new Date())]={h:8.2,q:4,t:1}")
    print('calm day', await A.evaluate("(()=>{const E=enData();return E.sc+' '+E.lv[1]})()"))
    await A.evaluate("delete S.check[iso(new Date())].stress"); print('old checkup (no stress)', await A.evaluate("(()=>{const E=enData();return E.stress+' '+E.P.find(x=>/Stress/.test(x.t)).ep})()"))
    await A.evaluate("S.check[iso(new Date())].stress=3;S.check[iso(new Date())].mood=0;save();renderAll()")
    await A.evaluate("openEnergy()"); await A.wait_for_timeout(150)
    print('energy sheet', await A.evaluate("document.querySelectorAll('#sheetBody .en-d').length"), 'badges', await A.evaluate("['ep-k','ep-i'].map(c=>document.querySelectorAll('#sheetBody .'+c).length>0).join(',')"), 'formula', await A.evaluate("/de base/.test($('#sheetBody').innerText)"))
    await A.screenshot(path='v121_energy.png')
    await A.evaluate("openWhy('energy')"); await A.wait_for_timeout(100); print('why energy', await A.evaluate("[...document.querySelectorAll('#sheetBody h3')].map(x=>x.textContent).join('|')"))
    await A.evaluate("openWhy('brief')"); await A.wait_for_timeout(100); print('why brief', await A.evaluate("[...document.querySelectorAll('#sheetBody h3')].map(x=>x.textContent).join('|')"), 'life', await A.evaluate("/Stress de vie/.test($('#sheetBody').innerText)"))
    await A.evaluate("closeSettings()")
    print('brief btn', await A.evaluate("(()=>{S.briefSeen=null;const h=briefCard();return h?/openWhy\\('brief'\\)/.test(h):'hors créneau'})()"))
    # --- mémoire
    await A.evaluate("openMem()"); await A.wait_for_timeout(100); print('mem empty', await A.evaluate("!!$('#sheetBody .mem-empty')"))
    await A.fill('#memNew','Je récupère mal après les nuits courtes'); await A.select_option('#memNewE','envisaged'); await A.select_option('#memNewT','hypothesis'); await A.locator('#sheetBody .btn', has_text='Ajouter').click(); await A.wait_for_timeout(100)
    await A.fill('#memNew','Je cours mieux le matin'); await A.select_option('#memNewE','known'); await A.locator('#sheetBody .btn', has_text='Ajouter').click(); await A.wait_for_timeout(100)
    await A.fill('#memNew','Je cours mieux le matin'); await A.locator('#sheetBody .btn', has_text='Ajouter').click(); await A.wait_for_timeout(100)
    print('mem', await A.evaluate("S.mem.length"), await A.evaluate("[...document.querySelectorAll('#sheetBody .mem-g')].map(x=>x.textContent).join('|')"))
    await A.screenshot(path='v121_mem.png')
    hid=await A.evaluate("S.mem.find(m=>m.type==='hypothesis').id")
    await A.locator(f'.mem-r[data-id="{hid}"] .chip', has_text='Corriger').click(); await A.fill('#memEd','Je récupère mal après les nuits de moins de 6 h'); await A.locator(f'.mem-r[data-id="{hid}"] .btn', has_text='Enregistrer').click(); await A.wait_for_timeout(100)
    print('edited', await A.evaluate(f"S.mem.find(m=>m.id==='{hid}').c"))
    await A.locator(f'.mem-r[data-id="{hid}"] .chip', has_text='Confirmer').click(); await A.wait_for_timeout(100)
    print('confirmed', await A.evaluate(f"(m=>m.st+' '+m.ep+' '+m.conf)(S.mem.find(m=>m.id==='{hid}'))"))
    await A.evaluate("memAdd({type:'hypothesis',ep:'envisaged',c:'La chaleur me ralentit beaucoup'},'user');renderMem()"); rid=await A.evaluate("S.mem.find(m=>/chaleur/.test(m.c)).id")
    await A.locator(f'.mem-r[data-id="{rid}"] .chip', has_text='Réfuter').click(); await A.wait_for_timeout(100)
    print('refuted', await A.evaluate(f"S.mem.find(m=>m.id==='{rid}').st"), await A.evaluate("/Hypothèses réfutées/.test($('#sheetBody').textContent)"))
    A.on('dialog',lambda d:asyncio.ensure_future(d.accept()))
    await A.locator(f'.mem-r[data-id="{rid}"] .chip', has_text='Supprimer').click(); await A.wait_for_timeout(150)
    print('deleted', await A.evaluate(f"!S.mem.some(m=>m.id==='{rid}')"), 'tomb', await A.evaluate(f"S.del.mem.includes('{rid}')"))
    await A.evaluate(f"S.mem.push({{id:'{rid}',type:'semantic',ep:'known',c:'revenant',st:'active',at:1,up:1}});applyTomb()"); print('tomb applied', await A.evaluate(f"!S.mem.some(m=>m.id==='{rid}')"))
    print('export no key', await A.evaluate("(()=>{let out='';const o=dlFile;dlFile=async(n,c)=>{out=n+' '+c.length+' '+/sk-ant|foulee_api/.test(c)};memExport();dlFile=o;return out})()"))
    await A.evaluate("closeSettings()")
    # --- coach
    await A.evaluate("localStorage.setItem('foulee_api','sk-test');CO().chat=[];save();openCoach()"); await A.wait_for_timeout(150)
    await A.evaluate("sendChat('Je fais quoi demain ?')"); await A.wait_for_timeout(700)
    b0=BODIES[0]; ctxj=b0['system'].split('(JSON) :\n')[1]
    print('system foulée', 'Intelligence Foulée' in b0['system'], 'mem ctx', len(json.loads(ctxj).get('memoire_foulee',[])), 'energy ctx', json.loads(ctxj).get('bourse_energie',{}).get('niveau'), 'check ctx', json.loads(ctxj).get('checkup_du_jour',{}).get('stress_de_vie'))
    last=await A.evaluate("CO().chat[CO().chat.length-1]")
    print('stripped', '<memoire>' not in last['text'], 'proposals', len(last.get('mp',[])), [x['ep'] for x in last.get('mp',[])])
    print('badges', await A.evaluate("['ep-k','ep-i','ep-e'].map(c=>document.querySelectorAll('#chatBox .'+c).length).join(',')"), 'raw tags left', await A.evaluate("/\\[SAVOIR\\]|\\[DÉDUIRE\\]/.test($('#chatBox').innerText)"), 'why', await A.evaluate("document.querySelectorAll('#chatBox .why-b').length"), 'memp', await A.evaluate("document.querySelectorAll('#chatBox .memp-r').length"))
    await A.screenshot(path='v121_coach.png')
    await A.evaluate("sayCoach(CO().chat[CO().chat.length-1].text)"); print('spoken w/o tags', await A.evaluate("!/\\[SAVOIR\\]/.test(window.__said.join(' '))"))
    await A.locator('#chatBox .memp-r .chip', has_text='Retenir').first.click(); await A.wait_for_timeout(100)
    await A.locator('#chatBox .memp-r .chip', has_text='Ignorer').first.click(); await A.wait_for_timeout(100)
    print('accepted', await A.evaluate("S.mem.filter(m=>m.src==='ai').map(m=>m.ep+':'+m.c).join('|')"), 'left', await A.evaluate("document.querySelectorAll('#chatBox .memp-r').length"))
    await A.locator('#chatBox .why-b').click(); await A.wait_for_timeout(700)
    b1=BODIES[-1]['messages'][-1]['content']; print('why sent', 'Pourquoi ?' in b1 and 'contre-exemples' in b1, 'why btn after', await A.evaluate("document.querySelectorAll('#chatBox .why-b').length"), 'user sees', await A.evaluate("[...document.querySelectorAll('#chatBox .msg.u')].pop().textContent"))
    await A.evaluate("closeCoach()")
    # --- Ton espace
    await A.evaluate("showTab('plus')"); await A.wait_for_timeout(250)
    print('space', await A.evaluate("['mem','energy'].map(k=>!!$('[data-page=plus] [data-k='+k+']')).join(',')"))
    await A.locator('[data-page=plus] [data-k=mem]').first.click(); await A.wait_for_timeout(150); print('open mem', await A.evaluate("/Ce que Foulée sait de moi/.test($('#sheetBody').innerText)"))
    await A.evaluate("closeSettings()")
    # --- iPad
    I=await br.new_context(viewport={'width':1194,'height':834}); C=await I.new_page(); C.on('pageerror',lambda x:errs.append('C '+str(x))); await setup(C)
    await C.goto('http://127.0.0.1:8765/index.html'); await C.wait_for_timeout(1700)
    await C.evaluate("loadDemo();S.check={};S.check[iso(new Date())]={fc:null,sore:1,mood:1,stress:2,motiv:1,pain:[],t:1};save();renderAll();showTab('today')"); await C.wait_for_timeout(300)
    print('ipad card', await C.evaluate("!!$('[data-page=today] .en-card')"), 'overflow', await C.evaluate("document.documentElement.scrollWidth>innerWidth"))
    await C.screenshot(path='v121_ipad.png'); await I.close()
    print('overflow phone', await A.evaluate("showTab('today');document.documentElement.scrollWidth>innerWidth"))
    print('ERR', errs)
    await br.close()
asyncio.run(m())
