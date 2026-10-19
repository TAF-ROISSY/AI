"""v8.5 : plan nutrition & hydratation (calcul, prises, sac, ravitos, rappels vocaux en course guidée) ; mode chaleur & voyage (journal météo, acclimatation sur 14 jours, météo automatique à l'ouverture)."""
import os, json
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;window._dn=Date.now.bind(Date);const _dn=window._dn;Date.now=()=>window.__now??_dn();
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};"""
async def meteo(r):
    hrs=[f"2026-10-19T{h:02d}:00" for h in range(24)]
    await r.fulfill(status=200,content_type='application/json',body=json.dumps({'current':{'temperature_2m':31,'relative_humidity_2m':70,'dew_point_2m':25},'hourly':{'time':hrs,'temperature_2m':[26+abs(12-h)*-.4+8 for h in range(24)],'dew_point_2m':[24]*24}}))
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':13.75,'longitude':100.5},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://api.open-meteo.com/v1/forecast**',meteo)
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    for c in [(50,10,15,8),(120,18,20,300),(200,26,32,1200),(330,22,55,2500)]:
        r=await A.evaluate(f"(()=>{{const R=fuelCalc({{min:{c[0]},T:{c[1]},km:{c[2]},dp:{c[3]},kg:72,aid:[]}});return [R.cph,R.fph,R.nph,R.tot.f,R.gels,R.bars,R.salt,R.prises.length]}})()")
        print('fuel', c[:2], r)
    # depuis la course objectif
    await A.evaluate("S.race={name:'Trail des Crêtes',date:(()=>{const d=new Date();d.setDate(d.getDate()+40);return iso(d)})(),km:32,dp:1400,aid:[10,21],temp:24};save();renderAll();showTab('courses')"); await A.wait_for_timeout(150)
    await A.locator('[data-page=courses] button:has-text("Nutrition")').first.click(); await A.wait_for_timeout(150)
    print('sheet', await A.evaluate("$('#sheetBody').innerText.toLowerCase().includes('plan de prises')"), 'ravito', await A.evaluate("$('#sheetBody').innerText.toLowerCase().includes('ravito km')"), 'def', await A.evaluate("JSON.stringify({min:FU.min,aid:FU.aid})"))
    await A.screenshot(path='f_sheet.png',full_page=True)
    await A.fill('#fu_h','1.5'); await A.locator('#fu_h').dispatch_event('change'); print('changed', await A.evaluate("FU.min"), await A.evaluate("$('#sheetBody').innerText.includes('45 g')"))
    await A.evaluate("closeSettings()")
    # rappels vocaux en sortie longue guidée (≈ 100 min)
    await A.evaluate("SREG.lx={k:'r0l',t:'Sortie longue 18 km',s:'18 km',icon:'⛰️'};grOpen('lx')"); print('fuelOn', await A.evaluate("GR.fuelOn+' '+GR.fuelCarb+' '+Math.round(grPlanMin(GR.steps))"))
    await A.evaluate("window.__now=_dn();window.__said=[];grStart();window.__said=[]")
    await A.evaluate("""(()=>{let lat=49.2,t=window.__now;for(let i=0;i<1400;i++){t+=3000;window.__now=t;lat+=3.0*3/111320;grFeed({t,lat,lon:2.5,acc:6});if(i%4===0)grTick();if(t-window.__now>0)break;}})()""")
    s=await A.evaluate("window.__said"); print('fuel said', [x for x in s if 'boire' in x or 'gel' in x][:3], len([x for x in s if 'boire' in x or 'gel' in x]))
    await A.evaluate("grStop(false);$('#grv').classList.remove('on');window.__now=null")
    # chaleur : météo auto + journal + acclimatation
    await A.evaluate("S.settings.heatAuto=true;S.heat=null;save();heatAutoRun()"); await A.wait_for_timeout(800)
    print('heat', await A.evaluate("JSON.stringify(S.heatLog[iso(new Date())])"), 'pct', await A.evaluate("Math.round(heatNow().pct*100)"))
    await A.evaluate("""(()=>{for(let i=1;i<9;i++){const d=new Date();d.setDate(d.getDate()-i);const k=iso(d);S.heatLog[k]={T:30,Tmax:33,Td:24,pct:.06};S.activities.push({id:770000+i,name:'Run chaud',sport_type:'Run',start_date_local:k+'T06:30:00Z',distance:9000,moving_time:3300,total_elevation_gain:20});}save();})()""")
    print('acclim', await A.evaluate("JSON.stringify((()=>{const a=acclim();return [a.n,a.pct,a.hotNow]})())"))
    await A.evaluate("showTab('today')"); await A.wait_for_timeout(200)
    print('card', await A.evaluate("$('[data-page=today]').innerText.includes('Acclimatation à la chaleur')"))
    await A.locator('[data-page=today] .card:has-text("Acclimatation")').first.screenshot(path='h_card.png')
    print('synced', await A.evaluate("'heatLog' in syncPayload().data"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
