"""v7.5 : export du plan d'entraînement complet dans le calendrier (.ics validé par icalendar)."""
import os, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
try: import icalendar
except ImportError: icalendar=None
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll();setMod('trail','plan')"); await A.wait_for_timeout(200)
    print('banner', await A.evaluate("document.querySelector('[data-page=plan]').innerText.includes('Plan dans mon calendrier')"))
    await A.evaluate("openPlanCal()"); await A.wait_for_timeout(100); await A.locator('#sheetBody').screenshot(path='t_plancal.png')
    n=await A.evaluate("planCalSessions().length"); nr=await A.evaluate("planCalSessions().filter(x=>x.run).length"); print('sessions', n, 'run', nr)
    async with A.expect_download() as dl: await A.evaluate("planCalGo()")
    print('file', (await dl.value).suggested_filename)
    ics=await A.evaluate("window.__lastIcs")
    if icalendar:
        cal=icalendar.Calendar.from_ical(ics); ev=list(cal.walk('VEVENT'))
        print('events', len(ev), 'all-day', all(not hasattr(e.decoded('DTSTART'),'hour') for e in ev), 'uids unique', len({str(e['UID']) for e in ev})==len(ev))
        print('first', str(ev[0]['SUMMARY']), '|', str(ev[0]['DESCRIPTION'])[:120].replace('\n',' / '))
    print('lines<=75', all(len(l.encode())<=75 for l in ics.split('\r\n')))
    await A.evaluate("PCD.str=false;openPlanCal()"); print('run only', await A.evaluate("planCalSessions().every(x=>x.run)"), await A.evaluate("planCalSessions().length"))
    await A.evaluate("PCD.from='all'"); print('whole cycle', await A.evaluate("planCalSessions().length"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
