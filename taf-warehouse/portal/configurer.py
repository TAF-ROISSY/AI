"""Renseigne les adresses du portail et met à jour l'empreinte CSP du script.

Usage : python portal/configurer.py https://ops.exemple.fr https://warehouse.exemple.fr
Écrit portal/dist/index.html (le modèle portal/index.html n'est pas modifié).
"""
import base64, hashlib, re, sys
from pathlib import Path

if len(sys.argv) != 3 or not all(re.fullmatch(r'https://[A-Za-z0-9.-]+(/[^\s\'"<>]*)?', u) for u in sys.argv[1:]):
    raise SystemExit(__doc__)
ops, warehouse = sys.argv[1:]
here = Path(__file__).resolve().parent
html = (here / 'index.html').read_text(encoding='utf-8')
html = html.replace('https://TAF-OPS.A-RENSEIGNER', ops).replace('https://staging.deat82862v504.amplifyapp.com', ops).replace('https://WAREHOUSE.A-RENSEIGNER', warehouse)
script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
digest = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode()
html = re.sub(r"script-src 'sha256-[^']+'", f"script-src 'sha256-{digest}'", html)
(here / 'dist').mkdir(exist_ok=True)
(here / 'dist' / 'index.html').write_text(html, encoding='utf-8')
print('Portail prêt :', here / 'dist' / 'index.html')
