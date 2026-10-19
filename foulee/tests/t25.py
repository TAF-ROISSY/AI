"""v7.2 : séances muscu avec matériel ou au poids du corps (callisthénie) — choix par défaut, bascule par séance, programme sans kettlebell, barre ou table, adaptations conservées."""
import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort()); await A.route('https://raw.githubusercontent.com/**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();S.mp={...MP(),equip:{...MP().equip,kb12:true,kb16:true,bar:false,rings:false}};S.ctx={};save();renderAll();setMod('muscu','renfo')"); await A.wait_for_timeout(300)
    print('default', await A.evaluate("defMode()"))
    # programme poids du corps : aucun exercice kettlebell, sur les 3 phases
    r=await A.evaluate("JSON.stringify([0,4,8].map(w=>['A','B','C'].map(k=>{const T=strSession(k,w,'bw');return T.items.map(i=>i.id).join(',');})))")
    print('bw program', r)
    print('no kb in bw', await A.evaluate("[0,1,2,3,4,5,6,7,8,9,10,11].every(w=>['A','B','C'].every(k=>strSession(k,w,'bw').items.every(i=>!hasT(i.id,'kb'))))"))
    print('cues ok', await A.evaluate("[0,4,8].every(w=>['A','B','C'].every(k=>strSession(k,w,'bw').items.every(i=>CUE[i.id]&&EXM[i.id]!==undefined||CUE[i.id])))"))
    # bascule d'une séance
    k=await A.evaluate("`s${Math.max(0,weekIdx())}B`"); w=await A.evaluate("Math.max(0,weekIdx())")
    print('kb B', await A.evaluate(f"strObj({w},'B').s"), '|', await A.evaluate(f"strObj({w},'B').timer.ex.join(',')"))
    await A.evaluate(f"setSMode('{k}','bw')")
    o=await A.evaluate(f"JSON.stringify((o=>({{icon:o.icon,s:o.s,ex:o.timer.ex}}))(strObj({w},'B')))"); print('bw B', o)
    print('other sessions kb', await A.evaluate(f"strObj({w},'A').icon"), 'override', await A.evaluate("JSON.stringify(SMODE().over)"))
    # sans barre : tractions remplacées par le rowing sous une table, raison affichée
    print('pullup → tablerow', await A.evaluate(f"strObj({w},'B').x.includes('Rowing inversé sous une table')"), await A.evaluate(f"strObj({w},'B').x.includes('↻ remplace tractions')"))
    await A.evaluate("S.mp.equip.bar=true;save()")
    print('with bar', await A.evaluate(f"strObj({w},'B').timer.ex.join(',')"), '|', await A.evaluate(f"strObj({w},'B').s"))
    # adaptations conservées : genou douloureux + silencieux sur le bas du corps poids du corps
    await A.evaluate(f"setSMode('s{w}A','bw');S.ctx={{...CTX(),silent:true,pains:['knee']}};save()")
    r=await A.evaluate(f"JSON.stringify(adaptSession({{...strSession('A',4,'bw')}}).items.map(i=>i.id+(i.from?'<-'+i.from+'('+i.why+')':'')))"); print('adapt knee+silent w4', r)
    r=await A.evaluate("JSON.stringify(adaptSession({...strSession('C',0,'bw')}).items.map(i=>i.id+(i.from?'<-'+i.from:'')))"); print('adapt silent C', r)
    await A.evaluate("S.ctx={};save();renderAll()")
    # interface : carte de choix + bascule sur les cartes, pas sur une séance faite
    await A.evaluate("setMod('muscu','renfo')"); await A.wait_for_timeout(150)
    print('mode card', await A.evaluate("document.querySelector('[data-page=renfo]').innerText.includes('Type de séances')"), 'switches', await A.evaluate("document.querySelectorAll('[data-page=renfo] .msw').length"))
    await A.locator('[data-page=renfo]').screenshot(path='q_renfo.png')
    await A.evaluate(f"S.done['s{w}C']=true;save();renderAll()"); print('done no switch', await A.evaluate("document.querySelectorAll('[data-page=renfo] .msw').length"))
    # défaut poids du corps : toutes les séances basculent, les surcharges identiques disparaissent
    await A.evaluate("setDefMode('bw')"); print('def bw', await A.evaluate(f"['A','B','C'].map(k=>strObj({w},k).icon).join('')"), await A.evaluate("JSON.stringify(SMODE().over)"))
    await A.evaluate(f"setSMode('s{w}A','kb')"); print('override kb', await A.evaluate(f"strObj({w},'A').icon"), await A.evaluate("JSON.stringify(SMODE().over)"))
    # sans kettlebell dans le profil : défaut poids du corps
    await A.evaluate("S.smode={over:{}};S.mp.equip={...S.mp.equip,kb8:false,kb12:false,kb16:false,kb20:false,kb24:false,pair:false};save()"); print('no kb default', await A.evaluate("defMode()"))
    # accueil muscu, chrono et carnet
    await A.evaluate("S.smode={over:{}};S.mp.equip.kb12=true;save();renderAll();setMod('muscu','muscu')"); await A.wait_for_timeout(150)
    print('home switch', await A.evaluate("document.querySelectorAll('[data-page=muscu] .msw').length>=0"))
    print('ctx', await A.evaluate("JSON.stringify({t:coachContext().muscu.type_seances,o:coachContext().muscu.seances_basculees})"))
    print('sync smode', await A.evaluate("'smode' in syncPayload().data"))
    for t in [['muscu','muscu'],['muscu','renfo'],['muscu','suivi'],['cross','cross']]:
        await A.evaluate(f"setMod('{t[0]}','{t[1]}')"); await A.wait_for_timeout(80)
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
