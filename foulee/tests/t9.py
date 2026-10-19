import os
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
AS=os.path.join(os.path.dirname(os.path.abspath(__file__)),'assets')
import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2);e=[];pg.on('pageerror',lambda x:e.append(str(x)))
        await pg.route('https://fonts.**',lambda r: r.abort())
        await pg.goto('file://'+APP+'/index.html'); await pg.evaluate("loadDemo()")
        print('n défis',await pg.evaluate("DEFIS.length"), 'gods',await pg.evaluate("GODS.length"))
        print('check ids', await pg.evaluate("DEFIS.flatMap(D=>D.it.map(x=>x[0])).filter(x=>!CUE[x])"))
        for g in ['zeus','poseidon','iris','kentauros','aphrodite']:
            print(g, await pg.evaluate(f"(()=>{{const D=DEF_ID('{g}'),its=defiPlan(D);return D.lv[2]+'t: '+its.map(x=>qty(D,2,0,x)+' '+x.id+(x.from?'<'+x.from:'')).join(', ')+' ≈'+estMin(D,2,its)+'min'}})()"))
        await pg.evaluate("S.ctx={silent:true,small:true,bw:false,dur:'std',pains:['knee'],legs:'off'};save();renderAll()")
        print('silent iris', await pg.evaluate("(()=>{const D=DEF_ID('iris'),its=defiPlan(D);return its.map(x=>qty(D,2,0,x)+' '+x.id).join(', ')})()"))
        print('silent kentauros', await pg.evaluate("(()=>{const D=DEF_ID('kentauros'),its=defiPlan(D);return its.map(x=>qty(D,2,0,x)+' '+x.id).join(', ')})()"))
        await pg.evaluate("S.ctx={...DEFCTX};save();renderAll();setMod('muscu','defis');defiCat='haut';renderDefis()")
        await pg.screenshot(path='g_cat.png',full_page=True)
        # Zeus avec repos accéléré
        await pg.evaluate("DEF_ID('zeus').rest=2;startDefi('zeus',0)"); await pg.click('#chGo'); await pg.wait_for_timeout(400)
        await pg.click('#chLap'); await pg.wait_for_timeout(500); await pg.screenshot(path='g_rest.png')
        print('rest round', await pg.inner_text('#chRound'))
        await pg.wait_for_timeout(2200); print('after rest', await pg.inner_text('#chRound'))
        for i in range(3): await pg.click('#chLap'); await pg.wait_for_timeout(2300)
        print('done', await pg.evaluate("JSON.stringify(S.ch.zeus)"))
        print(e); await b.close()
asyncio.run(m())
