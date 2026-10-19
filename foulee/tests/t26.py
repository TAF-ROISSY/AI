"""v7.3 : voix du coach, annonces du chrono (moitié, efforts restants, 10 s), course guidée GPS (km, cible, fractions, point à la demande), rattachement automatique des sorties Strava au programme."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];window.__now=null;window._dn=Date.now.bind(Date);const _dn=window._dn;Date.now=()=>window.__now??_dn();
const V=[{name:'Thomas',lang:'fr-FR',localService:true},{name:'Amélie (améliorée)',lang:'fr-CA',localService:true},{name:'Samantha',lang:'en-US',localService:true}];
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,cancel(){},getVoices(){return V;},speak(u){window.__said.push({t:u.text,v:u.voice&&u.voice.name,r:u.rate});}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;"""
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':49.2,'longitude':2.5},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();const d=dayIdx();S.sched={...SD(),q:d,e:(d+1)%7,l:(d+6)%7,A:(d+2)%7,B:(d+3)%7,C:(d+4)%7};S.links={};S.unlink={};save();renderAll()"); await A.wait_for_timeout(200)
    # voix
    print('voice', await A.evaluate("pickVoice().name"), '| fr only', await A.evaluate("frVoices().map(v=>v.name).join(',')"))
    await A.evaluate("S.settings.voiceName='Thomas';S.settings.voiceRate=1.2;window.__said=[];vSay('Kilomètre 3. Allure 5:42 /km.')")
    print('vSay', await A.evaluate("JSON.stringify(window.__said)"))
    await A.evaluate("openSettings()"); print('voice card', await A.evaluate("$('#s_voice').options.length"), await A.evaluate("$('#sheetBody').innerText.includes('Voix du coach')")); await A.evaluate("closeSettings()")
    # chrono : moitié, efforts restants, 10 s
    await A.evaluate("window.__said=[];useTimer({mode:'interval',work:4,rest:3,rounds:3,prep:1})"); await A.wait_for_timeout(100)
    await A.evaluate("document.querySelector('#chGo').click()"); await A.wait_for_timeout(19500)
    print('chrono', await A.evaluate("window.__said.map(x=>x.t).join(' | ')"))
    await A.evaluate("window.__said=[];useTimer({mode:'interval',work:30,rest:40,rounds:2,prep:0});CH.phases=buildPhases();CH.i=0;CH.rem=30;CH.running=true;CH.end=performance.now()+14000;chTick();CH.i=1;CH.rem=40;CH.end=performance.now()+9800;chTick();clearInterval(CH.iv);CH.running=false")
    print('half/10s', await A.evaluate("window.__said.map(x=>x.t).join(' | ')"))
    # course guidée : footing facile (km et cible)
    ke=await A.evaluate("runPlan(Math.max(0,weekIdx())).s.find(s=>/e$/.test(s.k)).k")
    await A.evaluate("renderAll()"); await A.evaluate(f"grOpen('{ke}')"); await A.wait_for_timeout(100)
    print('plan footing', await A.evaluate("JSON.stringify(GR.steps.map(s=>[s.k,s.d,s.t,Math.round(s.lo),Math.round(s.hi)]))"))
    await A.locator('#grv').screenshot(path='r_guide_start.png')
    await A.evaluate("window.__now=_dn();window.__said=[];grStart()")
    lo,hi=await A.evaluate("[GR.steps[0].lo,GR.steps[0].hi]")
    pace=(lo+hi)/2; v=1000/pace
    feed=f"""(()=>{{let lat=49.2,t=window.__now;for(let i=0;i<1100;i++){{t+=2000;window.__now=t;lat+={v}*2/111320;grFeed({{t,lat,lon:2.5,acc:6}});if(i%5===0)grTick();}}}})()"""
    await A.evaluate(feed)
    s=await A.evaluate("window.__said.map(x=>x.t)"); print('footing said', len(s), [x for x in s if 'Kilomètre' in x][:2], [x for x in s if 'Moitié' in x][:1])
    print('dist', await A.evaluate("Math.round(GR.dist)"), 'splits', await A.evaluate("GR.splits.length"))
    await A.evaluate("window.__said=[];grStatus()"); print('status', await A.evaluate("window.__said.map(x=>x.t).join(' ')"))
    await A.screenshot(path='r_guide_run.png')
    # trop rapide → alerte
    await A.evaluate("window.__said=[];GR.lastWarn=0;(()=>{let lat=GR.fix.lat,t=window.__now;for(let i=0;i<40;i++){t+=2000;window.__now=t;lat+=4.5*2/111320;grFeed({t,lat,lon:2.5,acc:6});}})()")
    print('fast warn', await A.evaluate("window.__said.map(x=>x.t).filter(x=>/rapide/.test(x)).slice(0,1)"))
    await A.evaluate("grStop(true);GR.si=GR.steps.length;grDraw()"); await A.wait_for_timeout(100)
    print('gps saved', await A.evaluate(f"JSON.stringify({{done:!!S.done['{ke}'],link:S.links['{ke}']&&S.links['{ke}'].src,km:S.links['{ke}']&&S.links['{ke}'].km,gruns:S.gruns.length,nosync:!('gruns' in syncPayload().data)}})"))
    await A.screenshot(path='r_guide_done.png'); await A.evaluate("$('#grv').classList.remove('on')")
    # course guidée : fractions de 400 m
    kq=await A.evaluate("(()=>{for(let w=0;w<12;w++){const s=runPlan(w).s.find(x=>/q$/.test(x.k)&&x.wk&&x.wk.work.d);if(s){SREG[s.k]=s;return s.k;}}})()")
    await A.evaluate(f"grOpen('{kq}')"); print('plan 400', await A.evaluate("JSON.stringify(GR.steps.slice(0,4).map(s=>[s.k,s.n,s.d,s.t,s.tp&&Math.round(s.tp)]))"))
    await A.evaluate("window.__now=_dn()+5e6;window.__said=[];grStart();grNext();window.__said=[]")
    tp=await A.evaluate("GR.steps[1].tp")
    await A.evaluate(f"""(()=>{{let lat=49.2,t=window.__now;const v=1000/{tp};for(let i=0;i<70;i++){{t+=2000;window.__now=t;lat+=v*2/111320;grFeed({{t,lat,lon:2.5,acc:5}});grTick();if(GR.si!==1)break;}}}})()""")
    print('rep said', await A.evaluate("window.__said.map(x=>x.t).join(' | ')"))
    await A.evaluate("window.__said=[];(()=>{let t=window.__now;for(let i=0;i<80;i++){t+=1000;window.__now=t;grTick();if(GR.si!==2)break;}})()")
    print('rest said', await A.evaluate("window.__said.map(x=>x.t).join(' | ')"))
    await A.evaluate("grStop(false);$('#grv').classList.remove('on')")
    # rattachement Strava : sortie longue faite hier (la veille du jour prévu), puis footing du jour
    kl=await A.evaluate("runPlan(Math.max(0,weekIdx())).s.find(s=>/l$/.test(s.k)).k")
    await A.evaluate(f"""(()=>{{delete S.links['{ke}'];S.done['{ke}']=false;const iso2=d=>{{const p=n=>String(n).padStart(2,'0');return `${{d.getFullYear()}}-${{p(d.getMonth()+1)}}-${{p(d.getDate())}}T07:30:00Z`;}};
      const lday=sessDate(Math.max(0,weekIdx()),SD().l),now=new Date();
      S.activities.push({{id:777001,name:'Footing du matin',sport_type:'Run',start_date_local:iso2(now),distance:8200,moving_time:2950,total_elevation_gain:40,average_heartrate:138,poly:''}});
      A=null;save();}})()""")
    print('linked', await A.evaluate("linkPlan()"), await A.evaluate(f"JSON.stringify(S.links['{ke}']||S.links[Object.keys(S.links)[0]])"))
    print('which', await A.evaluate("JSON.stringify(Object.entries(S.links).map(([k,l])=>[k,l.id]))"))
    k1=await A.evaluate("Object.entries(S.links).find(([k,l])=>l.id===777001)[0]")
    print('done', await A.evaluate(f"S.done['{k1}']"), 'line', await A.evaluate(f"strip(linkLine(SREG['{k1}']||runPlan(Math.max(0,weekIdx())).s.find(s=>s.k==='{k1}')))"))
    print('no double', await A.evaluate("linkPlan()"))
    await A.evaluate("renderAll();setMod('trail','plan')"); await A.wait_for_timeout(150); await A.locator('[data-page=plan] .sess:has(.lk)').first.screenshot(path='r_linked.png')
    await A.evaluate(f"unlinkRun('{k1}')"); print('unlinked', await A.evaluate(f"JSON.stringify({{l:!!S.links['{k1}'],d:S.done['{k1}'],u:S.unlink['{k1}']}})"), 'not relinked', await A.evaluate("linkPlan()")==0)
    # voix du coach dans le chat et le Coach du jour
    await A.evaluate("CO().chat=[{role:'user',text:'Salut',t:1},{role:'assistant',text:'**Bravo** pour ta sortie. Demain repos.',t:2}];save();openCoach()"); await A.wait_for_timeout(100)
    print('chat spk', await A.evaluate("document.querySelectorAll('#chatBox .mspk').length"))
    await A.evaluate("window.__said=[];document.querySelector('#chatBox .mspk').click()"); print('coach said', await A.evaluate("window.__said.map(x=>x.t).join(' ')"))
    await A.evaluate("closeCoach();setMod('trail','trail')"); print('cdj spk', await A.evaluate("!![...document.querySelectorAll('[data-page=trail] details.cdj .ib')].find(b=>b.textContent.includes('🔊'))"))
    for t in [['trail','trail'],['trail','plan'],['muscu','muscu'],['cross','cross']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(60)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
