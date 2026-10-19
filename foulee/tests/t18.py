import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.add_init_script("window.__said=[];Object.defineProperty(window,'speechSynthesis',{configurable:true,get(){return {speaking:false,cancel(){},speak(u){window.__said.push(u.text)}};}});window.SpeechSynthesisUtterance=function(t){this.text=t};")
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.settings.fcrest=50;S.settings.fcmax=185;save();renderAll()"); await A.wait_for_timeout(300)
    # HR classification
    print('cls', await A.evaluate("JSON.stringify((()=>{const a=getA();const c={};a.runs.forEach(r=>c[a.cls(r)]=(c[a.cls(r)]||0)+1);return c;})())"))
    # KB + pair
    await A.evaluate("S.mp={...MP(),equip:{...MP().equip,kb8:true,kb12:true,kb16:false,kb20:true,kb24:false,pair:true}};save();renderAll()")
    print('kbList', await A.evaluate("kbList(MP())"), 'defKg w5', await A.evaluate("(()=>{const s=S.settings.start;return defKg('goblet')})()"))
    r=await A.evaluate("JSON.stringify(adaptSession({...strSession('A',5),when:new Date(Date.now()+5*864e5)}).items.map(i=>i.id+(i.from?'<-'+i.from+'('+i.why+')':'')))")
    print('A w5', r)
    r=await A.evaluate("JSON.stringify(adaptSession({...strSession('B',5),when:new Date(Date.now()+5*864e5)}).items.map(i=>i.id+(i.from?'<-'+i.from+'('+i.why+')':'')))")
    print('B w5', r)
    print('strObj label', await A.evaluate("strObj(5,'A').s"))
    await A.evaluate("S.mp={...MP(),equip:{...MP().equip,pair:false}};save()")
    print('no pair', await A.evaluate("JSON.stringify(adaptSession({...strSession('A',5)}).items.map(i=>i.id))"))
    await A.evaluate("openProfile()"); await A.wait_for_timeout(100); await A.screenshot(path='j_prof.png')
    # custom exo
    await A.evaluate("closeSettings();setMod('muscu','suivi')"); await A.wait_for_timeout(200)
    await A.evaluate("openLog('free_'+iso(new Date()),'Séance libre',[],{})"); await A.wait_for_timeout(100)
    await A.fill('#cx_n','Tirage poulie'); await A.select_option('#cx_g','dos'); await A.evaluate("cxAdd()"); await A.wait_for_timeout(100)
    await A.screenshot(path='j_log.png')
    await A.evaluate("LOGD.rows[0].sets=[{kg:35,r:10},{kg:35,r:10},{kg:40,r:8}];saveLog()")
    print('custom', await A.evaluate("JSON.stringify({c:S.customExo,log:S.log.filter(l=>l.ex.startsWith('cx_')),dos:muscleWeek().dos})"))
    print('lib excludes', await A.evaluate("Object.keys(CUE).filter(id=>!/^(sk|cx)_/.test(id)).includes('dblsq')"))
    # voice
    await A.evaluate("useTimer({mode:'interval',work:3,rest:2,rounds:2,prep:1,ex:['goblet','push']})"); await A.wait_for_timeout(200)
    await A.evaluate("document.querySelector('#chGo').click()"); await A.wait_for_timeout(9000)
    print('said', await A.evaluate("JSON.stringify(window.__said)"))
    await A.evaluate("window.__said=[];readSess(Object.keys(SREG).find(k=>/^s\\d+A$/.test(k))||Object.keys(SREG)[0])")
    print('read', await A.evaluate("window.__said.slice(0,4)"), await A.evaluate("window.__said.length"))
    # coach history
    await A.evaluate("CO().chat=[{role:'user',text:'Salut',t:Date.now()-6e4},{role:'assistant',text:'**Bonjour** !',t:Date.now()}];CO().review={d:iso(new Date()),b:{titre:'Bilan S1',resume:'Bonne semaine.',points_forts:['Régulier'],vigilance:[],ajustements:[{module:'trail',action:'Ajoute 2 km'}],message:''}};save();renderAll();openCoachHist('chat')"); await A.wait_for_timeout(200)
    await A.screenshot(path='j_hist.png')
    await A.evaluate("openCoachHist('bilans')"); print('bilans', await A.evaluate("CO().reviews.length"), await A.evaluate("document.querySelector('#sheetBody').innerText.includes('Ajoute 2 km')"))
    await A.evaluate("CO().review={d:iso(new Date(Date.now()+864e5)),b:{titre:'Bilan S2',resume:'X',points_forts:[],vigilance:[],ajustements:[],message:''}};renderAll()"); print('reviews kept', await A.evaluate("CO().reviews.map(r=>r.b.titre)"))
    await A.evaluate("openCoachHist('seances')")
    for t in [['trail','trail'],['trail','plan'],['muscu','muscu'],['muscu','renfo'],['muscu','suivi'],['cross','cross'],['cross','forme']]:
        await A.evaluate(f"closeSettings();setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
