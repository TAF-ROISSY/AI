"""v9.5 : carnet en vrai PDF (jsPDF chargé à la demande, partage du fichier, lien Ouvrir, repli impression, hors ligne)."""
import os, base64
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
NM='/tmp/claude-0/v95/node_modules'
import asyncio, subprocess, time
from playwright.async_api import async_playwright
async def lib(route):
    u=route.request.url
    f=NM+('/jspdf/dist/jspdf.umd.min.js' if 'autotable' not in u else '/jspdf-autotable/dist/jspdf.plugin.autotable.min.js')
    await route.fulfill(status=200,content_type='application/javascript',body=open(f,encoding='utf-8').read())
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    # hors ligne : CDN bloqué
    await A.route('https://cdn.jsdelivr.net/**',lambda r:r.abort()); await A.route('https://cdnjs.cloudflare.com/**',lambda r:r.abort()); await A.route('https://unpkg.com/**',lambda r:r.abort())
    await A.evaluate("printBook()"); await A.wait_for_timeout(500); print('offline toast', await A.evaluate("$('#toast').textContent"))
    await A.unroute('https://cdn.jsdelivr.net/**'); await A.unroute('https://unpkg.com/**'); await A.route('https://cdn.jsdelivr.net/**',lib)
    await A.evaluate("(()=>{const d=new Date();d.setDate(d.getDate()+40);S.race={name:'Trail des Crêtes',date:iso(d),km:32,dp:1500};S.check=S.check||{};S.check[iso(new Date())]={pain:[{z:'achille',lv:2}]};save()})()")
    await A.evaluate("printBook()"); await A.wait_for_timeout(1500)
    print('pdf', await A.evaluate("JSON.stringify(window.__pdf)"), 'sheet', await A.evaluate("$('#sheetBody').innerText.includes('Carnet PDF prêt')"), 'link', await A.evaluate("!!$('#sheetBody a[download]')"))
    await A.screenshot(path='v95_sheet.png')
    b64=await A.evaluate("(async()=>{const b=await BOOKF.arrayBuffer();let s='';const u=new Uint8Array(b);for(let i=0;i<u.length;i++)s+=String.fromCharCode(u[i]);return btoa(s)})()")
    open('carnet.pdf','wb').write(base64.b64decode(b64))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
