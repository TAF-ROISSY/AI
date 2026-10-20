"""v9.9 : télécommande Apple Watch / AirPods via Media Session (« À l’écoute ») pour la course guidée et le chrono : titre, pause, reprise, étape suivante, point vocal."""
import os, json, subprocess
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, time
from playwright.async_api import async_playwright
INIT="""window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,pending:false,cancel(){},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},speak(u){window.__said.push(u.text);}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};navigator.vibrate=()=>true;HTMLMediaElement.prototype.play=function(){return Promise.resolve();};
window.__msH={};const _sah=navigator.mediaSession.setActionHandler.bind(navigator.mediaSession);navigator.mediaSession.setActionHandler=(a,f)=>{window.__msH[a]=f;try{_sah(a,f)}catch(e){}};"""
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,geolocation={'latitude':45.9,'longitude':6.1},permissions=['geolocation'])
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(INIT); await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(2300)
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    k=await A.evaluate("(()=>{for(let w=0;w<12;w++)for(let d=0;d<7;d++){const o=daySessions(w,d,'run').find(x=>/q$/.test(x.k));if(o)return o.k;}})()"); print('session', k)
    await A.evaluate(f"grOpen('{k}')"); print('hint', await A.evaluate("$('#grBody').innerText.includes('Télécommande Apple Watch')"))
    await A.locator('#grBody button:has-text("Démarrer")').first.click(); await A.wait_for_timeout(1300)
    print('meta', await A.evaluate("JSON.stringify({t:navigator.mediaSession.metadata&&navigator.mediaSession.metadata.title,a:navigator.mediaSession.metadata&&navigator.mediaSession.metadata.artist,st:navigator.mediaSession.playbackState,h:Object.keys(window.__msH).filter(x=>window.__msH[x])})"))
    await A.evaluate("window.__msH.pause()"); await A.wait_for_timeout(100); print('pause', await A.evaluate("GR.paused"), await A.evaluate("navigator.mediaSession.playbackState"), await A.evaluate("navigator.mediaSession.metadata.title"))
    await A.evaluate("window.__msH.play()"); print('play', await A.evaluate("GR.paused"))
    si=await A.evaluate("GR.si"); await A.evaluate("window.__msH.nexttrack()"); print('next', si, '→', await A.evaluate("GR.si"), await A.evaluate("navigator.mediaSession.metadata.title"))
    await A.evaluate("window.__said=[];window.__msH.previoustrack()"); print('prev', await A.evaluate("window.__said.join(' / ').slice(0,90)"))
    await A.evaluate("grStop(false);$('#grv').classList.remove('on')"); await A.wait_for_timeout(1300); print('cleared', await A.evaluate("navigator.mediaSession.metadata===null"))
    # chrono
    await A.evaluate("showTab('chrono')"); await A.wait_for_timeout(200); await A.locator('#chGo').click(); await A.wait_for_timeout(1300)
    print('chrono meta', await A.evaluate("JSON.stringify({run:CH.running,mode:CH.mode,t:navigator.mediaSession.metadata&&navigator.mediaSession.metadata.title,a:navigator.mediaSession.metadata&&navigator.mediaSession.metadata.artist})"))
    await A.evaluate("window.__msH.pause()"); print('ch pause', await A.evaluate("CH.running")); await A.evaluate("window.__msH.play()"); print('ch play', await A.evaluate("CH.running"))
    i=await A.evaluate("CH.i"); await A.evaluate("window.__msH.nexttrack()"); await A.wait_for_timeout(400); print('ch next', i, '→', await A.evaluate("CH.i"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
