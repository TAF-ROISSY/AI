"""v7.4.1 + v7.7 : voix sur iPhone (session audio « lecture » pour passer outre le mode silencieux, bips de secours) — déblocage au premier toucher, pas de cancel() + speak() différé dans un toucher, énoncés gardés en mémoire, diagnostic « Tester la voix »."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from playwright.async_api import async_playwright
MOCK="""window.__said=[];window.__mute=%s;let _sp=false;
Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {get speaking(){return _sp;},pending:false,cancel(){window.__said.push('<cancel>');_sp=false;},resume(){},getVoices(){return [{name:'Thomas',lang:'fr-FR',localService:true}];},
 speak(u){window.__said.push({t:u.text,vol:u.volume,lang:u.lang});if(!window.__mute&&u.text.trim()){_sp=true;setTimeout(()=>{u.onstart&&u.onstart();setTimeout(()=>{_sp=false;u.onend&&u.onend();},200);},30);}}};}});
window.SpeechSynthesisUtterance=function(t){this.text=t};
window.__aud=0;navigator.audioSession={type:'auto'};const _P=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.__aud++;return Promise.resolve();};"""
async def run(br,mute):
    ctx=await br.new_context(viewport={'width':390,'height':844}); A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script(MOCK%('true' if mute else 'false')); await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html'); await A.wait_for_timeout(300)
    await A.mouse.click(200,400); await A.wait_for_timeout(100)
    first=await A.evaluate("window.__said[0]"); print('mute' if mute else 'son', 'unlock', first, 'VX.ok', await A.evaluate("VX.ok"))
    await A.evaluate("openSettings()"); await A.wait_for_timeout(100)
    await A.locator('#sheetBody button:has-text("Tester la voix")').click(); await A.wait_for_timeout(3700)
    print('  diag', (await A.evaluate("$('#s_vdiag').textContent"))[:60], '| session', await A.evaluate("navigator.audioSession.type"), '| media plays', await A.evaluate("window.__aud>0"), '| fallback beeps', await A.evaluate("VX.fail||0"))
    print('  utts kept', await A.evaluate("Array.isArray(VX.utts)"), 'said', await A.evaluate("window.__said.filter(x=>x.t).map(x=>x.t).slice(1,3)"))
    if not mute:
        # coupure pendant une phrase depuis un toucher : cancel puis parole immédiate (pas de délai)
        await A.evaluate("window.__said=[]"); await A.locator('#sheetBody button:has-text("Tester la voix")').click(); await A.wait_for_timeout(700)
        await A.locator('#sheetBody button:has-text("Tester la voix")').click(); await A.wait_for_timeout(650)
        print('  tap during speech', await A.evaluate("JSON.stringify(window.__said.map(x=>x.t?x.t.slice(0,12):x))"))
    print('  ERR',errs); await ctx.close()
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); await run(br,False); await run(br,True); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
