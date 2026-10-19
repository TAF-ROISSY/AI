"""v7.8 : Traces de trail — itinéraires OpenStreetMap (Overpass) autour de moi ou d'un lieu (Nominatim), D+ par relief (Open-Meteo), filtres, carte, fiche, GPX, favoris synchronisés."""
import os, json, math
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time, io
from PIL import Image
im=Image.new('RGB',(256,256),(210,214,200)); _b=io.BytesIO(); im.save(_b,'PNG'); TILE=_b.getvalue()
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')+'/'
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
C=(49.42,2.83)
def circle(cx,cy,rkm,n=80,a0=0,a1=2*math.pi):
    return [(cx+rkm/111*math.sin(a0+(a1-a0)*i/(n-1)), cy+rkm/(111*math.cos(math.radians(cx)))*math.cos(a0+(a1-a0)*i/(n-1))) for i in range(n)]
def way(pts): return [{'lat':a,'lon':b} for a,b in pts]
def rel(i,tags,segs): return {'type':'relation','id':i,'tags':{'type':'route',**tags},'members':[{'type':'way','ref':i*100+k,'role':'','geometry':g} for k,g in enumerate(segs)]}
loop=circle(C[0]+.02,C[1],2.0)            # boucle ≈ 12,5 km
q1,q2,q3=loop[:30],loop[29:60],loop[59:]
line=[(C[0]-.05+i*.002,C[1]-.06+i*.003) for i in range(60)]   # ≈ 20 km
gr=[{'lat':C[0]+.1-i*.004,'lon':C[1]+.05} for i in range(50)]; gr[25]=None   # GR coupé (tronçon)
run=circle(C[0]-.01,C[1]+.02,.8,40)
OV={'elements':[
  rel(1,{'route':'hiking','name':'Boucle des Beaux Monts','network':'lwn','ref':'PR 3'},[way(q1),way(list(reversed(q2))),way(q3)]),
  rel(2,{'route':'hiking','name':'Sentier des Étangs','network':'lwn','from':'Pierrefonds','to':'Vieux-Moulin'},[way(line)]),
  rel(3,{'route':'hiking','name':'GR 12','network':'nwn','ref':'GR 12','distance':'400'},[gr]),
  rel(4,{'route':'running','name':'Parcours trail permanent'},[way(run)]),
]+[{'type':'way','id':100+k,'tags':{'highway':'path','surface':'ground'}} for k in range(3)]+[{'type':'way','id':200,'tags':{'highway':'residential','surface':'asphalt'}},{'type':'way','id':400,'tags':{'highway':'track'}}]}
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':C[0],'longitude':C[1]},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    calls={'ov':0,'el':0,'nom':0}
    async def ov(r):
        calls['ov']+=1; assert 'around' in r.request.post_data; await r.fulfill(status=200,content_type='application/json',body=json.dumps(OV))
    async def el(r):
        calls['el']+=1; q=parse_qs(urlparse(r.request.url).query); la=q['latitude'][0].split(','); await r.fulfill(status=200,content_type='application/json',body=json.dumps({'elevation':[round(80+60*math.sin(i/len(la)*math.pi*4),1) for i in range(len(la))]}))
    async def nom(r):
        calls['nom']+=1; await r.fulfill(status=200,content_type='application/json',body=json.dumps([{'lat':str(C[0]),'lon':str(C[1]),'display_name':'Compiègne, Oise, Hauts-de-France, France'}]))
    await A.route('https://overpass-api.de/**',ov); await A.route('https://api.open-meteo.com/v1/elevation**',el); await A.route('https://nominatim.openstreetmap.org/**',nom)
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://cdnjs.cloudflare.com/**',lambda r: r.fulfill(path=D+('leaflet.css' if r.request.url.endswith('.css') else 'leaflet.js')))
    await A.route('https://*.tile.opentopomap.org/**',lambda r: r.fulfill(body=TILE,content_type='image/png'))
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll();setMod('trail','courses')"); await A.wait_for_timeout(200)
    print('card', await A.evaluate("!!$('#trCard')"))
    await A.fill('#tr_place','Compiègne'); await A.locator('#trCard button:has-text("Chercher")').click(); await A.wait_for_timeout(1500)
    print('calls', calls, 'zone', await A.evaluate("TR.cn"))
    print('list', await A.evaluate("JSON.stringify(TR.list.map(o=>[o.n,Math.round(o.km*10)/10,o.loop,o.pieces,o.sent,o.net,o.clip,o.dp]))"))
    await A.locator('#trCard').screenshot(path='t_list.png')
    # filtres
    async def cnt(js): return await A.evaluate(f"(()=>{{{js};return trFilter().length}})()")
    print('boucle', await cnt("TR.f.loop='loop'"), 'aller', await cnt("TR.f.loop='line'"), '| GR', await cnt("TR.f.loop='all';TR.f.net='gr'"), 'run', await cnt("TR.f.net='run'"), '| nature≥75', await cnt("TR.f.net='all';TR.f.path=75"))
    print('dist 10-20', await cnt("TR.f.path=0;TR.f.dist='b'"), '| D+ <300', await cnt("TR.f.dist='all';TR.f.dp='lo'"), '| texte étang', await cnt("TR.f.dp='all';TR.f.q='étang'"))
    print('tri D+', await A.evaluate("TR.f.q='';TR.f.sort='dp';trFilter().map(o=>o.dp).join(',')"), '| tri près', await A.evaluate("TR.f.sort='near';trFilter().map(o=>o.n.slice(0,8)).join('|')"))
    await A.evaluate("TR.fOpen=true;TR.f.path=50;renderCourses()"); await A.wait_for_timeout(100)
    print('nbF', await A.evaluate("trNbF()"), 'summary', await A.evaluate("$('#trCard details summary').textContent"))
    await A.locator('#trCard').screenshot(path='t_filters.png'); await A.evaluate("TR.f.path=0;renderCourses()")
    # fiche + GPX
    await A.evaluate("trOpen('r1')"); await A.wait_for_timeout(500)
    print('sheet', await A.evaluate("$('#sheetBody').innerText.includes('Boucle des Beaux Monts')"), 'profile', await A.evaluate("!!$('#sheetBody svg.chart')"), 'time', await A.evaluate("[...document.querySelectorAll('.tr-kpi')].map(k=>k.innerText.replace(/\\n/,': ')).join(' | ')"))
    await A.screenshot(path='t_sheet.png')
    g=await A.evaluate("trGpxStr(trById('r1'))"); print('gpx', g.count('<trkpt'), g.count('<trkseg>'), 'opendatacommons' in g)
    g3=await A.evaluate("trGpxStr(trById('r3'))"); print('gpx GR segs', g3.count('<trkseg>'))
    # favoris + synchro + tombstone
    await A.evaluate("trFav('r1',true)"); print('fav', await A.evaluate("JSON.stringify(S.trFav.map(x=>[x.id,x.km,x.dp,x.loop]))"), 'synced', await A.evaluate("'trFav' in syncPayload().data"))
    await A.evaluate("trFav('r1',false)"); print('unfav tomb', await A.evaluate("JSON.stringify(S.del.trfav)"))
    await A.evaluate("S.trFav=[{id:'r1',n:'x',km:1}];applyTomb()"); print('tomb applied', await A.evaluate("S.trFav.length"))
    await A.evaluate("closeSettings()")
    # autour de moi + carte + cache D+
    calls['el']=0; await A.evaluate("TR.list=[];TR.cn='';TR.c=null;renderCourses()")
    await A.locator('#trCard button:has-text("Autour de moi")').click(); await A.wait_for_timeout(1500)
    print('me', await A.evaluate("TR.cn"), len(await A.evaluate("TR.list")), 'elev from cache', calls['el']==0)
    await A.evaluate("TR.map=true;renderCourses()"); await A.wait_for_timeout(1200)
    print('map lines', await A.evaluate("document.querySelectorAll('#trMap path.leaflet-interactive').length"))
    await A.locator('#trCard').screenshot(path='t_map.png')
    # erreur réseau
    await A.unroute('https://overpass-api.de/**'); await A.route('https://overpass-api.de/**',lambda r:r.fulfill(status=504,body='')); await A.route('https://overpass.kumi.systems/**',lambda r:r.fulfill(status=504,body=''))
    await A.evaluate("trSearch()"); await A.wait_for_timeout(800); print('err', await A.evaluate("TR.err&&TR.err.slice(0,40)"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
