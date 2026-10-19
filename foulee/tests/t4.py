import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2)
        errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto('file://'+APP+'/index.html')
        await pg.evaluate('loadDemo()')
        await pg.evaluate("showTab('muscu')")
        await pg.screenshot(path='n_home.png',full_page=True)
        # bilan
        await pg.evaluate('openProfile()')
        await pg.fill('#t_push','18'); await pg.fill('#t_squat','42'); await pg.fill('#t_plank','70')
        await pg.screenshot(path='n_profile.png')
        await pg.evaluate('saveProfile()')
        # adaptation : silencieux + poids du corps + genoux + express
        await pg.evaluate("S.ctx={silent:true,small:false,bw:true,dur:'express',pains:['knee'],legs:'off'};save();renderAll()")
        for k in ['A','B','C']:
            T=await pg.evaluate(f"(()=>{{const T=adaptSession(strSession('{k}',0));return T.items.map(i=>i.id+(i.from?'<'+i.from:'')+' '+i.p).join(' | ')+' || timer '+JSON.stringify(T.timer)+' || '+T.notes.join(';')}})()")
            print(k,T)
        T=await pg.evaluate("(()=>{const T=adaptSession(strSession('A',9));return T.items.map(i=>i.id+(i.from?'<'+i.from:'')+' '+i.p).join(' | ')+' || '+JSON.stringify(T.timer)})()")
        print('P3 A',T)
        await pg.evaluate("showTab('renfo')")
        await pg.evaluate("document.querySelectorAll('[data-page=renfo] details').forEach(d=>d.open=true)")
        await pg.screenshot(path='n_renfo.png',full_page=True)
        # legs auto
        await pg.evaluate("S.ctx={...DEFCTX};save();renderAll()")
        print('legsTired',await pg.evaluate("legsTired()"))
        # feedback détaillé avec douleur
        await pg.evaluate("toggleDone('s0A')")
        await pg.screenshot(path='n_fb.png')
        await pg.evaluate("mfb.d5=2;mfb.pains=['shoulder'];saveMuscuFb()")
        print('ctx pains',await pg.evaluate("CTX().pains"), 'adjA',await pg.evaluate("adj('A')"))
        # défi échelle
        await pg.evaluate("startDefi('annapurna',0)")
        await pg.click('#chGo')
        for i in range(5):
            await pg.wait_for_timeout(250)
            if i==1: await pg.screenshot(path='n_ladder.png')
            await pg.click('#chLap')
        await pg.wait_for_timeout(200)
        await pg.evaluate("mfb.d5=3;mfb.te='propre';saveMuscuFb()")
        print('unlock',await pg.evaluate("unlocked(DEF_ID('annapurna'),1)"))
        await pg.evaluate("showTab('suivi')")
        await pg.screenshot(path='n_prog.png',full_page=True)
        await pg.evaluate("showTab('defis')")
        await pg.screenshot(path='n_defis.png',full_page=True)
        print('ERR',errs)
        await b.close()
asyncio.run(main())
