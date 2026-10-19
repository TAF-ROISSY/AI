"""v7.4 : envoi d'une séance guidée à l'Apple Watch (lien fouleewatch://), format compatible avec GuidedRun.swift ; analyse syntaxique des fichiers Swift (pip install tree-sitter tree-sitter-swift)."""
import os, json, base64, glob
APP=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import asyncio, subprocess, time
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
def dec(u):
    d=parse_qs(urlparse(u).query)['d'][0]; d+='='*(-len(d)%4)
    return json.loads(base64.urlsafe_b64decode(d).decode('utf-8'))
def check(p,label):
    ok=isinstance(p['id'],str) and isinstance(p['name'],str) and len(p['steps'])>0
    for s in p['steps']:
        ok=ok and set(s)=={'n','k','d','t','lo','hi','tp'} and s['k'] in ('warm','work','rest','cool','run') and bool(s['d'] or s['t'])
        ok=ok and all(s[x] is None or isinstance(s[x],(int,float)) for x in 'd t lo hi tp'.split())
    print(label,'format Swift', bool(ok), '|', p['name'], '|', [(s['k'],s['d'],s['t'],s['lo'],s['hi'],s['tp']) for s in p['steps'][:4]])
async def m():
  async with async_playwright() as p:
    br=await p.chromium.launch(); ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
    A=await ctx.new_page(); errs=[]; A.on('pageerror',lambda x:errs.append(str(x)))
    await A.route('https://fonts.**',lambda r:r.abort())
    await A.goto('http://127.0.0.1:8765/index.html')
    await A.evaluate("loadDemo();renderAll()"); await A.wait_for_timeout(200)
    ke=await A.evaluate("(()=>{const s=runPlan(Math.max(0,weekIdx())).s.find(x=>/e$/.test(x.k));SREG[s.k]=s;return s.k;})()")
    u=await A.evaluate(f"watchUrl(SREG['{ke}'])"); print('scheme', u[:26], 'len', len(u)); check(dec(u),'footing')
    kq=await A.evaluate("(()=>{for(let w=0;w<12;w++){const s=runPlan(w).s.find(x=>/q$/.test(x.k)&&x.wk&&x.wk.work.d);if(s){SREG[s.k]=s;WKREG[s.k]=s;return s.k;}}})()")
    pq=dec(await A.evaluate(f"watchUrl(SREG['{kq}'])")); check(pq,'400 m'); print('steps', len(pq['steps']), 'works', sum(1 for s in pq['steps'] if s['k']=='work'))
    kl=await A.evaluate("(()=>{const s=runPlan(Math.max(0,weekIdx())).s.find(x=>/l$/.test(x.k));SREG[s.k]=s;return s.k;})()")
    check(dec(await A.evaluate(f"watchUrl(SREG['{kl}'])")),'longue')
    # accents et caractères spéciaux
    print('utf8', dec(await A.evaluate("watchUrl({k:'r0e',t:'Footing « léger » · 8 km',s:'8 km · 5:20–6:00/km'})"))['name'])
    # boutons
    await A.evaluate(f"grOpen('{ke}')"); await A.wait_for_timeout(100)
    print('btn guided', await A.evaluate("$('#grBody').innerText.includes('Envoyer à l’Apple Watch')"))
    await A.locator('#grv').screenshot(path='s_watch_btn.png')
    await A.evaluate(f"sendWatch('{ke}')"); await A.wait_for_timeout(400)
    print('sent', (await A.evaluate("window.__lastWatchUrl||''"))[:26], await A.evaluate(f"!!S.watchSent['{ke}']"), 'nosync', await A.evaluate("!('watchSent' in syncPayload().data)"))
    await A.evaluate("$('#grv').classList.remove('on')"); await A.evaluate(f"openWkExport('{kq}')"); print('btn export', await A.evaluate("$('#sheetBody').innerText.includes('Envoyer à l’Apple Watch')"))
    print('ERR',errs); await br.close()
srv=subprocess.Popen(['python3','-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
try: asyncio.run(m())
finally: srv.terminate()
# Swift : analyse syntaxique
try:
    import tree_sitter_swift as tss
    from tree_sitter import Language, Parser
    P=Parser(Language(tss.language()))
    for f in sorted(glob.glob(os.path.join(APP,'watch','**','*.swift'),recursive=True)):
        src=open(f,'rb').read(); bad=[]
        def walk(n):
            if n.type=='ERROR' or n.is_missing: bad.append(n.start_point[0]+1)
            for c in n.children: walk(c)
        walk(P.parse(src).root_node)
        print('swift', os.path.relpath(f,APP), 'OK' if not bad else 'ERREURS lignes '+str(bad[:5]))
except ImportError:
    print('swift : tree-sitter-swift absent (pip install tree-sitter tree-sitter-swift)')
