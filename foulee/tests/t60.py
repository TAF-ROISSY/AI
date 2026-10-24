"""v12.2 : learning & emotion — débrief à chaud (carte après une séance, émotion, victoires déclarées, note, mémoire, plus tard, effacer + tombstone), victoires invisibles (détection, carte, toast une fois, fiche), boussole Ego vs Body (ego → séance Flow, body → allègement, Pourquoi ?), chronique de la semaine (locale, rédigée par Foulée avec mémoire proposée, navigation), contexte du coach, Ton espace, iPad."""
import json, asyncio
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
BODIES=[]
CHR=("Cette semaine, tu as bouclé tes séances malgré une journée de mardi sous pression. [SAVOIR] La sortie de jeudi t’a laissé une sensation libératrice. "
     "Tu repars lundi avec de la marge.\n<memoire>[{\"type\":\"lesson\",\"ep\":\"inferred\",\"c\":\"Courir après une journée stressante me libère\",\"conf\":0.6}]</memoire>")
async def api(route):
    BODIES.append(json.loads(route.request.post_data or '{}'))
    await route.fulfill(status=200,content_type='application/json',body=json.dumps({"content":[{"type":"text","text":CHR}],"stop_reason":"end_turn"}))
async def setup(pg):
    await pg.add_init_script(INIT)
    for u in ['https://fonts.**','https://cdnjs.cloudflare.com/**','https://*open-meteo.com/**','https://overpass**','https://api.github.com/**','https://*.tile.**']:
        await pg.route(u,lambda r:r.abort())
    await pg.route('https://api.anthropic.com/**',api)
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]
    ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2); A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append(str(x))); await setup(A)
    A.on('dialog',lambda d:asyncio.ensure_future(d.accept()))
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(1800)
    print('version', await A.evaluate("APP_VER"))
    await A.evaluate("loadDemo();S.check={};S.mem=[];S.deb={};S.sleep={};S.vicSeen=[];S.vicToast=null;S.adj={};S.debSkip=[];(()=>{const w=weekIdx(),d=dayIdx();daySessions(w,d).forEach(o=>{S.done[o.k]=false;if(S.links)delete S.links[o.k]});})();save();renderAll();showTab('today')"); await A.wait_for_timeout(300)
    T="[data-page=today]"
    print('no checkup: ego', await A.evaluate("egoBody()"), 'cards', await A.evaluate(f"['.eb-c','.deb-c'].map(c=>!!$('{T} '+c)).join(',')"))
    # --- débrief à chaud : une séance cochée aujourd'hui
    k=await A.evaluate("(()=>{const w=weekIdx();for(let d=0;d<7;d++){const o=daySessions(w,d).find(x=>x&&x.k&&!x.str&&/^r/.test(x.k));if(o)return o.k;}return null})()")
    print('session', k is not None)
    await A.evaluate(f"S.done['{k}']=true;S.doneAt=S.doneAt||{{}};S.doneAt['{k}']=Date.now()-20*60000;save();renderAll()"); await A.wait_for_timeout(200)
    print('deb card', await A.evaluate(f"!!$('{T} .deb-c')"), await A.evaluate(f"$('{T} .deb-c p').textContent.slice(0,60)"))
    await A.screenshot(path='v122_debcard.png')
    await A.locator(f'{T} .deb-c .chip', has_text='Libérateur').click(); await A.wait_for_timeout(150)
    print('sheet emo on', await A.evaluate("$('#sheetBody .chip.on').textContent"))
    await A.locator('#sheetBody .chip', has_text='J’y suis allé malgré la flemme').click()
    await A.fill('#dbT','Parti énervé du boulot, je rentre léger.')
    await A.locator('#sheetBody input[type=checkbox]').check()
    await A.screenshot(path='v122_debrief.png')
    await A.locator('#sheetBody .btn', has_text='Enregistrer').click(); await A.wait_for_timeout(200)
    d=await A.evaluate(f"S.deb['{k}']"); print('saved', d['emo'], d['vic'], d['note'][:20], d['keep'], 'title', bool(d['t']))
    print('mem sensation', await A.evaluate("S.mem.filter(m=>m.type==='sensation'&&m.src==='debrief'&&m.ep==='known').length"), 'card gone', await A.evaluate(f"!$('{T} .deb-c')"))
    await A.evaluate(f"openDebrief('{k}')"); await A.wait_for_timeout(100); await A.locator('#sheetBody .btn', has_text='Enregistrer').click(); await A.wait_for_timeout(100)
    print('re-save no dup mem', await A.evaluate("S.mem.filter(m=>m.type==='sensation').length"))
    await A.evaluate("const g=Date.now();S.gruns=[...(S.gruns||[]),{id:g,k:null,d:iso(new Date()),start:new Date(Date.now()-50*60000).toISOString(),km:5,t:1800,splits:[],steps:[],pts:[]}];save();renderAll()")
    print('free run card', await A.evaluate(f"!!$('{T} .deb-c')"))
    await A.locator(f'{T} .deb-c .ib').click(); await A.wait_for_timeout(150); print('skipped', await A.evaluate(f"!$('{T} .deb-c')"), await A.evaluate("S.debSkip.length"))
    await A.evaluate("S.deb['zz']={k:'zz',emo:'lourd',vic:[],note:'',t:'X',d:iso(new Date()),at:1,up:1};DBX={k:'zz'};delDebrief();S.deb['zz']={k:'zz',emo:'lourd',vic:[],d:iso(new Date()),at:1};applyTomb()")
    print('tomb deb', await A.evaluate("!S.deb.zz&&S.del.deb.includes('zz')"))
    # --- victoires invisibles
    await A.evaluate("S.check[iso(new Date())]={fc:null,sore:0,mood:3,stress:1,motiv:0,pain:[],t:Date.now()};save();renderAll()"); await A.wait_for_timeout(1300)
    V=await A.evaluate("vicList().map(v=>v.id.split(':')[0])"); print('vic', sorted(set(V)))
    print('vic card', await A.evaluate(f"!!$('{T} .vic-c')"), 'toast', await A.evaluate("($('#toast')||{}).textContent||''"))
    n1=await A.evaluate("S.vicSeen.length"); await A.evaluate("renderAll()"); await A.wait_for_timeout(200); print('toast once', await A.evaluate("S.vicToast===iso(new Date())"), n1==await A.evaluate("S.vicSeen.length"))
    await A.evaluate("for(let i=0;i<8;i++){const d=iso(new Date(Date.now()-i*DAY));S.check[d]=S.check[d]||{fc:null,sore:0,mood:2,stress:1,motiv:2,pain:[],t:1};S.sleep[d]={h:7.5,q:3,t:1};}");
    V2=await A.evaluate("vicList().map(v=>v.id.split(':')[0])"); print('streak+sleep', 'chk' in V2, 'sleep' in V2)
    await A.evaluate("S.mv=S.mv||{};S.mv['rXtest']={drop:1,w:0,d:0,from:iso(new Date(Date.now()-DAY))}"); print('drop vic', 'drop' in await A.evaluate("vicList().map(v=>v.id.split(':')[0])"))
    await A.evaluate("openVic()"); await A.wait_for_timeout(100); print('vic sheet', await A.evaluate("document.querySelectorAll('#sheetBody .mem-r').length"))
    await A.evaluate("closeSettings()")
    # --- boussole Ego vs Body
    await A.evaluate(f"S.done['{k}']=false;S.check[iso(new Date())]={{fc:null,sore:0,mood:3,stress:2,motiv:0,pain:[],t:Date.now()}};S.sleep[iso(new Date())]={{h:8.2,q:4,t:1}};save();renderAll()"); await A.wait_for_timeout(200)
    E=await A.evaluate("(()=>{const E=egoBody();return E.q+' '+E.body+' '+E.mind})()"); print('ego', E)
    print('eb card', await A.evaluate(f"!!$('{T} .eb-c')"), await A.evaluate(f"$('{T} .eb-c .eb-t').textContent"), 'stress note', await A.evaluate("/soupape/.test(egoBody().x)"))
    await A.screenshot(path='v122_today.png', full_page=True)
    nx=await A.evaluate("(()=>{const T=todayFirst();return T&&T.next?T.next.k:null})()")
    if nx:
        await A.locator(f'{T} .eb-c .btn', has_text='séance Flow').click(); await A.wait_for_timeout(200)
        print('flow', await A.evaluate(f"S.adj['{nx}'].action+' '+S.adj['{nx}'].titre"), 'hero', await A.evaluate(f"$('{T} .f-hero-t').textContent.slice(0,20)"))
        await A.evaluate(f"delete S.adj['{nx}']")
    else:
        await A.evaluate(f"flowApply('{k}')"); print('flow (direct)', await A.evaluate(f"S.adj['{k}'].action+' '+S.adj['{k}'].titre"), await A.evaluate(f"/Sortie Flow/.test(sessByKey('{k}').t)")); await A.evaluate(f"delete S.adj['{k}']")
    await A.evaluate("S.check[iso(new Date())]={fc:null,sore:3,mood:0,stress:1,motiv:3,pain:[{z:'mollet',lv:2}],t:Date.now()};S.sleep[iso(new Date())]={h:5.2,q:1,t:1};save();renderAll()"); await A.wait_for_timeout(200)
    print('body', await A.evaluate("egoBody().q"), await A.evaluate(f"$('{T} .eb-c .eb-t').textContent"))
    if nx:
        await A.locator(f'{T} .eb-c .btn', has_text='Alléger').click(); await A.wait_for_timeout(200); print('light', await A.evaluate(f"S.adj['{nx}'].action"))
    await A.evaluate("openWhy('ego')"); await A.wait_for_timeout(100); print('why ego', await A.evaluate("[...document.querySelectorAll('#sheetBody h3')].map(x=>x.textContent).join('|')"))
    await A.evaluate("closeSettings()")
    print('old checkup no motiv', await A.evaluate("(()=>{const c=S.check[iso(new Date())];delete c.motiv;return egoBody()})()"))
    # --- chronique
    X=await A.evaluate("(()=>{const X=chronData(new Date());return {deb:X.D.length,dom:X.dom,v:X.V.length,txt:chronLocal(X)}})()"); print('chron', X['deb'], X['dom'], X['v']>0, '|', X['txt'][:140])
    print('chron card fn', await A.evaluate("typeof chronCard()==='string'"))
    await A.evaluate("localStorage.setItem('foulee_api','sk-test');openChron(iso(mondayOf(new Date())))"); await A.wait_for_timeout(150)
    print('chron sheet', await A.evaluate("$('#sheetBody .chr-nav b').textContent"), 'stats', await A.evaluate("document.querySelectorAll('#sheetBody .chr-st div').length"), 'next disabled', await A.evaluate("$('#sheetBody .chr-nav .chip:last-child').disabled"))
    await A.screenshot(path='v122_chron_local.png')
    await A.locator('#chrGo').click(); await A.wait_for_timeout(700)
    b=BODIES[-1]; u=b['messages'][0]['content']
    print('ai sent', 'chronique' in u and 'debriefs' in u, 'foulée sys', 'Intelligence Foulée' in b['system'])
    print('ai text', await A.evaluate("CHR()[iso(mondayOf(new Date()))].ai.slice(0,40)"), 'no tags', await A.evaluate("!/\\[SAVOIR\\]|<memoire>/.test($('#sheetBody .chr-txt').textContent)"), 'memp', await A.evaluate("document.querySelectorAll('#sheetBody .memp-r').length"))
    await A.screenshot(path='v122_chron_ai.png')
    await A.locator('#sheetBody .memp-r .chip', has_text='Retenir').click(); await A.wait_for_timeout(150)
    print('mem lesson', await A.evaluate("S.mem.some(m=>m.type==='lesson'&&m.src==='ai')"), 'memp left', await A.evaluate("document.querySelectorAll('#sheetBody .memp-r').length"))
    await A.locator('#sheetBody .chr-nav .chip').first.click(); await A.wait_for_timeout(150); print('prev week', await A.evaluate("$('#sheetBody .chr-nav b').textContent"))
    await A.evaluate("closeSettings()")
    # --- contexte coach
    c=await A.evaluate("coachContext()"); print('ctx', 'debriefs_recents' in c, len(c.get('debriefs_recents',[])), 'victoires_invisibles_7j' in c, 'boussole_ego_body' in c)
    # --- Ton espace
    await A.evaluate("showTab('plus')"); await A.wait_for_timeout(250)
    print('space', await A.evaluate("['chron','vic','debrief'].map(k=>!!$('[data-page=plus] [data-k='+k+']')).join(',')"))
    await A.locator('[data-page=plus] [data-k=debrief]').first.click(); await A.wait_for_timeout(150); print('open debrief', await A.evaluate("/Débrief à chaud/.test($('#sheetBody').innerText)"))
    await A.evaluate("closeSettings()")
    print('overflow phone', await A.evaluate("showTab('today');document.documentElement.scrollWidth>innerWidth"))
    I=await br.new_context(viewport={'width':1194,'height':834}); C=await I.new_page(); C.on('pageerror',lambda x:errs.append('C '+str(x))); await setup(C)
    await C.goto('http://127.0.0.1:8765/index.html'); await C.wait_for_timeout(1700)
    await C.evaluate("loadDemo();S.check={};S.check[iso(new Date())]={fc:null,sore:0,mood:3,stress:2,motiv:0,pain:[],t:1};save();renderAll();showTab('today')"); await C.wait_for_timeout(300)
    print('ipad eb', await C.evaluate("!!$('[data-page=today] .eb-c')"), 'overflow', await C.evaluate("document.documentElement.scrollWidth>innerWidth"))
    await C.screenshot(path='v122_ipad.png'); await I.close()
    print('ERR', errs)
    await br.close()
asyncio.run(m())
