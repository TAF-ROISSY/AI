import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, subprocess, time, sys
from playwright.async_api import async_playwright
OUT=sys.argv[1] if len(sys.argv)>1 else 'z'
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=1)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.settings.fcrest=50;S.done.s0A=true;S.race={name:'Trail des Lacs',date:iso(new Date(Date.now()+40*864e5)),km:30,dp:1500,aid:[]};save();renderAll()"); await A.wait_for_timeout(500)
    await A.evaluate("document.querySelectorAll('.toast,#toast').forEach(e=>e.remove())")
    pages=[('trail','trail'),('trail','histo'),('trail','analyse'),('trail','plan'),('muscu','muscu'),('muscu','renfo'),('muscu','figures'),('muscu','defis'),('muscu','suivi'),('cross','cross'),('cross','forme')]
    for mo,t in pages:
        await A.evaluate(f"setMod('{mo}','{t}');window.scrollTo(0,0)"); await A.wait_for_timeout(250)
        h=await A.evaluate("document.documentElement.scrollHeight")
        await A.screenshot(path=f'{OUT}_{mo}_{t}.png',full_page=True); print(mo,t,h)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
