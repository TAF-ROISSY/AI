"""v8.7 : cartes hors ligne (tuiles d'une trace en cache, service worker, liste, suppression), bilan de la semaine en image, défis entre amis (gist secret agrégé, lien #ami=, classement, retrait)."""
import os, json, io
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from PIL import Image
from playwright.async_api import async_playwright
im=Image.new('RGB',(256,256),(200,210,190)); b=io.BytesIO(); im.save(b,'PNG'); TILE=b.getvalue()
gists={'fff111aaa222bbb333cc':{'files':{'foulee-defi.json':{'content':None,'truncated':False}}}}
tiles=[];gh_calls=[]
async def gh(r):
    req=r.request; gh_calls.append((req.method,req.url))
    if req.method=='POST':
        body=json.loads(req.post_data); gists['mine00000000000000000']={'files':{k:{'content':v['content'],'truncated':False} for k,v in body['files'].items()}}
        await r.fulfill(status=201,content_type='application/json',body=json.dumps({'id':'mine00000000000000000'})); return
    if req.method=='PATCH': await r.fulfill(status=200,content_type='application/json',body='{}'); return
    gid=req.url.rsplit('/',1)[1]
    if gid in gists: await r.fulfill(status=200,content_type='application/json',body=json.dumps(gists[gid]))
    else: await r.fulfill(status=404,body='')
async def m():
  ym=time.strftime('%Y-%m')
  gists['fff111aaa222bbb333cc']['files']['foulee-defi.json']['content']=json.dumps({'v':1,'pseudo':'Annabelle','maj':'2026-10-19T08:00:00Z','mois':{ym:{'km':87.5,'dp':2100,'h':11.2,'n':12}}})
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,accept_downloads=True)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.github.com/**',gh)
    async def tile(r): tiles.append(r.request.url); await r.fulfill(body=TILE,content_type='image/png',headers={'Access-Control-Allow-Origin':'*'})
    await A.route('https://*.tile.opentopomap.org/**',tile)
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    # cartes hors ligne
    pts="[[45.90,6.10],[45.93,6.14],[45.96,6.12],[45.92,6.08]]"
    print('tiles', await A.evaluate(f"(()=>{{const t=tileList({pts});return [t.urls.length,t.zmax,t.urls[0].replace(/\\d+/g,'#')]}})()"))
    print('big', await A.evaluate("(()=>{const t=tileList([[45.5,6.0],[46.2,6.9]]);return [t.urls.length,t.zmax]})()"))
    n=await A.evaluate(f"offSave('tr1','Boucle test',{pts})"); print('saved', n, len(tiles), 'cached', await A.evaluate("caches.open('foulee-tiles').then(c=>c.keys()).then(k=>k.length)"))
    n2=len(tiles); await A.evaluate(f"offSave('tr1','Boucle test',{pts})"); print('no refetch', len(tiles)-n2)
    await A.evaluate("openOffline()"); print('list', await A.evaluate("$('#sheetBody').innerText.includes('Boucle test')"))
    await A.evaluate("offDel('tr1')"); await A.wait_for_timeout(200); print('deleted', await A.evaluate("Object.keys(offAll()).length"), await A.evaluate("caches.open('foulee-tiles').then(c=>c.keys()).then(k=>k.length)"))
    await A.evaluate("closeSettings()")
    # bilan de la semaine
    print('stats', await A.evaluate("JSON.stringify((()=>{const s=weekStats(weekIdx()-1);return [Math.round(s.km),Math.round(s.dp),s.f,s.n,s.runs,!!s.best]})())"))
    await A.evaluate("navigator.canShare=()=>false")
    async with A.expect_download() as dl: await A.evaluate("shareWeek(weekIdx()-1)")
    d=await dl.value; path=await d.path(); print('image', d.suggested_filename, os.path.getsize(path)>20000)
    import shutil; shutil.copy(path,'w_week.png')
    print('sunday fn', await A.evaluate("typeof sundayBanner()"), 'rings share btn', await A.evaluate("!!$('[data-page=today] button[aria-label=\"Partager ma semaine\"]')"))
    # défis entre amis
    await A.evaluate("setVC({token:'ghp_test'});S.settings.pseudo='Christophe';save()")
    print('payload', await A.evaluate("JSON.stringify(defiPayload().mois[Object.keys(defiPayload().mois)[0]])"))
    print('publish', await A.evaluate("defiPublish()"), await A.evaluate("S.defiMe.gist"), 'files', list(gists['mine00000000000000000']['files'].keys()))
    print('content private', 'poly' not in gists['mine00000000000000000']['files']['foulee-defi.json']['content'], json.loads(gists['mine00000000000000000']['files']['foulee-defi.json']['content'])['pseudo'])
    print('link', await A.evaluate("defiLink().split('#')[1]"))
    await A.evaluate("defiPublish(true)"); print('patch', [m_ for m_,u in gh_calls].count('PATCH'))
    # ouverture d'un lien d'ami
    await A.goto('http://127.0.0.1:8765/index.html#ami=fff111aaa222bbb333cc'); await A.wait_for_timeout(1500)
    print('friend added', await A.evaluate("JSON.stringify((S.friends||[]).map(f=>f.id))"), 'hash cleared', await A.evaluate("location.hash===''"))
    print('board', await A.evaluate("[...document.querySelectorAll('#sheetBody .fr')].map(e=>e.innerText.replace(/\\s+/g,' ').trim()).join(' | ')"))
    await A.screenshot(path='d_board.png')
    await A.evaluate("FR.metric='dp';openDefis(true)"); print('by D+', await A.evaluate("$('#sheetBody .fr b').textContent"))
    await A.goto('http://127.0.0.1:8765/index.html#ami=mine00000000000000000'); await A.wait_for_timeout(500); print('own link ignored', await A.evaluate("(S.friends||[]).length"))
    await A.evaluate("defiDel('fff111aaa222bbb333cc')"); print('removed', await A.evaluate("(S.friends||[]).length"), await A.evaluate("S.del.friends.includes('fff111aaa222bbb333cc')"))
    await A.evaluate("openDefis(true)"); print('bad link', await A.evaluate("S.friends=[{id:'deadbeefdeadbeefdead'}];defiFetch().then(()=>FR.data['deadbeefdeadbeefdead'].ok)"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
