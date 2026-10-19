"""Lance toute la suite de tests Foulée (Playwright + Chromium headless).
Usage : python3 tests/run.py            (tous les tests)
        python3 tests/run.py t16 t17    (certains tests)
Les captures d'écran sont écrites dans tests/out/."""
import os, sys, subprocess, time, runpy, glob
HERE=os.path.dirname(os.path.abspath(__file__)); APP=os.path.abspath(os.path.join(HERE,'..'))
OUT=os.path.join(HERE,'out'); os.makedirs(OUT,exist_ok=True); os.chdir(OUT)
names=sys.argv[1:] or sorted([os.path.basename(f)[:-3] for f in glob.glob(os.path.join(HERE,'t*.py'))],key=lambda n:int(n[1:]))
for n in names:
    f=os.path.join(HERE,n+'.py'); src=open(f).read(); print('=====',n,flush=True)
    srv=None
    if 'subprocess.Popen' not in src:
        srv=subprocess.Popen([sys.executable,'-m','http.server','8765'],cwd=APP,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
    try: runpy.run_path(f,run_name='__main__')
    except SystemExit: pass
    except Exception as e: print('ÉCHEC',n,e)
    finally:
        if srv: srv.terminate()
