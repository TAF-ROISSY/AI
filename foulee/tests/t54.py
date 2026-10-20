"""v10.2 : notifications push (abonnement simulé auprès du serveur, test, désactivation, mise à jour à chaque changement), zones (maison, rayon, distance max, « à la maison », arrivée détectée), adresse du serveur transmise par le lien Foulée Suivi, notifications dans Foulée, gestionnaires push du service worker."""
import os, json, subprocess, time
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio
from playwright.async_api import async_playwright
G1='a'*32; NOW=int(time.time()*1000); SRV={'sub':[],'test':0,'unsub':0}
LIVE={'v':1,'pseudo':'Lucas','st':'run','name':'Footing','t0':NOW-900e3,'upd':NOW,'el':900,'dist':2500,'pos':[45.91,6.1],'trk':[[45.9,6.1],[45.91,6.1]],'route':None,'rest':None,'eta':None,'sos':False}
INIT="""Object.defineProperty(window,'Notification',{configurable:true,value:Object.assign(function(t,o){window.__notif=(window.__notif||[]).concat([t]);},{permission:'granted',requestPermission:async()=>'granted'})});
const fakeSub={endpoint:'https://push.example.com/xyz',toJSON(){return {endpoint:this.endpoint,keys:{p256dh:'BPk',auth:'au'}}},unsubscribe:async()=>true};let has=false;
if(window.PushManager){PushManager.prototype.subscribe=async function(){has=true;return fakeSub};PushManager.prototype.getSubscription=async function(){return has?fakeSub:null};}
const _reg=navigator.serviceWorker;Object.defineProperty(navigator,'serviceWorker',{configurable:true,value:{register:async()=>({}),ready:Promise.resolve({pushManager:{subscribe:async()=>{has=true;return fakeSub},getSubscription:async()=>has?fakeSub:null}})}});
window.PushManager=window.PushManager||function(){};"""
async def push(route):
    r=route.request;u=r.url
    if u.endswith('/vapid'): await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'key':'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U'}));return
    b=json.loads(r.post_data or '{}');k=u.rsplit('/',1)[1]
    if k=='sub': SRV['sub'].append(b)
    else: SRV[k]=SRV.get(k,0)+1
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'ok':True}))
async def gh(route):
    LIVE['upd']=int(time.time()*1000)
    await route.fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'files':{'foulee-live.json':{'content':json.dumps(LIVE)}}}))
async def setup(pg):
    await pg.add_init_script(INIT); await pg.route('https://fonts.**',lambda r:r.abort()); await pg.route('https://api.github.com/**',gh); await pg.route('https://push.test/**',push); await pg.route('https://cdnjs.cloudflare.com/**',lambda r:r.abort())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); errs=[]; ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.95,'longitude':6.1},permissions=['geolocation'])
    W=await ctx.new_page(); W.on('pageerror',lambda x:errs.append('W '+str(x))); await setup(W)
    await W.goto(f'http://127.0.0.1:8765/suivi.html#add={G1}&n=Lucas|push='+'https%3A%2F%2Fpush.test'); await W.wait_for_timeout(1000)
    print('push url', await W.evaluate("PUSH.url"), 'people', await W.evaluate("P.length"))
    await W.evaluate("openPush()"); print('sheet', await W.evaluate("document.querySelector('#shb').innerText.includes('Activer les notifications')"))
    await W.locator('#shb button:has-text("Activer")').click(); await W.wait_for_timeout(800)
    print('subscribed', await W.evaluate("PUSH.on"), 'srv sub', len(SRV['sub']), json.dumps(SRV['sub'][-1]['people']) if SRV['sub'] else '', SRV['sub'][-1].get('tz') if SRV['sub'] else '')
    await W.locator('#shb button:has-text("test")').click(); await W.wait_for_timeout(300); print('test sent', SRV.get('test'), await W.evaluate("document.querySelector('#pmsg').textContent"))
    await W.screenshot(path='v102_push.png'); await W.evaluate("closeSh()")
    # zones
    await W.evaluate("openEdit(0)"); await W.locator('#shb button:has-text("Ma position actuelle")').click(); await W.wait_for_timeout(500)
    print('home', await W.evaluate("JSON.stringify(P[0].home)")); await W.fill('#ef','3'); await W.locator('#shb .btn.pri').click(); await W.wait_for_timeout(1700)
    print('resync', len(SRV['sub']), json.dumps(SRV['sub'][-1]['people'][0]))
    await W.evaluate("tick(true)"); await W.wait_for_timeout(500); await W.evaluate("zoneCheck()")
    print('zone txt', await W.evaluate("zoneTxt(P[0])"))
    LIVE['pos']=[45.9502,6.1]; await W.evaluate("tick(true)"); await W.wait_for_timeout(500); await W.evaluate("zoneCheck()")
    print('arrived', await W.evaluate("window.__arrived||0"), await W.evaluate("zoneTxt(P[0])")); await W.screenshot(path='v102_home.png')
    await W.evaluate("openPush()"); await W.locator('#shb button:has-text("Désactiver")').click(); await W.wait_for_timeout(400); print('off', await W.evaluate("PUSH.on"), SRV.get('unsub'))
    # Foulée
    A=await ctx.new_page(); A.on('pageerror',lambda x:errs.append('A '+str(x))); await setup(A)
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate(f"loadDemo();fwAdd('{G1}','Lucas');S.settings.pushUrl='https://push.test';save();openFollow(true)")
    print('push card', await A.evaluate("$('#sheetBody').innerText.includes('Notifications (même appli fermée)')"), 'link', (await A.evaluate("fwLink(true)")).split('#')[1][-40:])
    n=len(SRV['sub']); await A.evaluate("pushMe()"); await A.wait_for_timeout(700); print('foulee sub', len(SRV['sub'])-n, json.dumps(SRV['sub'][-1]['people']))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
