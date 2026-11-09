import os,base64,uuid,pytest


@pytest.fixture(autouse=True)
def driver_for_receipts(monkeypatch):
    """Lot 19 : le chauffeur (remettant) est obligatoire à l'entrée. Les tests qui créent une réception
    sans le préciser reçoivent un chauffeur de test, créé avec les mêmes droits que la requête."""
    from starlette.testclient import TestClient as _TC
    original = _TC.post
    def post(self, url, *a, **kw):
        body = kw.get('json')
        if str(url).endswith('/api/receipts') and isinstance(body, dict) and 'driver_id' not in body and not kw.pop('_no_driver', False):
            import sys
            server = sys.modules.get('app.server')
            if server is not None:
                with server.db() as db:   # insertion directe : un seul chauffeur par base, sans audit
                    if not db.execute("SELECT id FROM drivers WHERE id='DRV-TEST'").fetchone():
                        db.execute("INSERT INTO drivers(id,name,company,plate,phone,created,id_type,id_number) VALUES('DRV-TEST','Chauffeur Test','Transports Test','','',?, 'CNI','T0000')", (server.now(),))
                kw['json'] = {**body, 'driver_id': 'DRV-TEST'}
        return original(self, url, *a, **kw)
    monkeypatch.setattr(_TC, 'post', post)
@pytest.fixture(autouse=True)
def test_mfa_key(monkeypatch):
    monkeypatch.setenv("TAF_MFA_ENCRYPTION_KEY",base64.urlsafe_b64encode(b"test-only-key-for-warehouse-1234").decode())


@pytest.fixture(autouse=True)
def postgres_schema(monkeypatch):
    """Avec TAF_TEST_DATABASE_URL, chaque test tourne sur PostgreSQL dans un schéma neuf."""
    base=os.getenv('TAF_TEST_DATABASE_URL','')
    if not base:
        monkeypatch.delenv('TAF_DATABASE_URL',raising=False);yield;return
    import psycopg
    schema='t_'+uuid.uuid4().hex[:12]
    with psycopg.connect(base,autocommit=True) as c:c.execute(f'CREATE SCHEMA {schema}')
    sep='&' if '?' in base else '?'
    monkeypatch.setenv('TAF_DATABASE_URL',f'{base}{sep}options=-csearch_path%3D{schema}')
    yield
    with psycopg.connect(base,autocommit=True) as c:c.execute(f'DROP SCHEMA {schema} CASCADE')


# Jeu d'essai partagé des lots 1 et suivants.
import importlib, tempfile
from fastapi.testclient import TestClient

PWD = 'TestPassword12345!'


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR'] = tmp
        os.environ['TAF_ADMIN_PASSWORD'] = PWD
        from app import server
        importlib.reload(server)
        c = TestClient(server.app)

        def login(name):
            r = c.post('/api/login', json={'username': name, 'password': PWD})
            assert r.status_code == 200, r.text
            return {'Authorization': 'Bearer ' + r.json()['token']}

        admin = login('admin')
        for name, role in [('expl', 'exploitation'), ('expl2', 'exploitation'), ('mag', 'worker'), ('resp', 'manager'), ('expl_mar', 'exploitation'), ('mag_mar', 'worker')]:
            r = c.post('/api/users', headers=admin, json={'username': name, 'password': PWD, 'role': role, 'warehouses': {'expl': ['Afrique', 'Maritime'], 'expl_mar': ['Maritime'], 'mag_mar': ['Maritime']}.get(name, ['Afrique'])})
            assert r.status_code == 200, r.text
        h = {'admin': admin, **{n: login(n) for n in ('expl', 'expl2', 'mag', 'resp', 'expl_mar', 'mag_mar')}}
        client_id = c.get('/api/clients', headers=admin).json()[0]['id']

        def receipt(expected=4, actual=4):
            r = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': client_id, 'expected': expected, 'actual': actual, 'weight': 400})
            assert r.status_code == 200, r.text
            return r.json()['id']

        def unit(rec, quantity=4, weight=400, who='mag', headers=None, placed=True, **extra):
            """Crée une unité ; par défaut elle est ensuite rangée en zone temporaire (lot 3)."""
            body = {'receipt_id': rec, 'description': 'Palette', 'quantity': quantity, 'weight': weight, 'volume': 1, 'dimensions_ok': True, **extra}
            r = c.post('/api/units', headers={**h[who], **(headers or {})}, json=body)
            if placed and r.status_code == 200:
                with server.db() as db:
                    db.execute("UPDATE units SET location_id='AFR-TEMP',status='available' WHERE id=? AND status='awaiting_putaway'", (r.json()['id'],))
            return r

        def get_unit(uid_):
            return next(x for x in c.get('/api/units', headers=admin).json() if x['id'] == uid_)

        yield {'c': c, 'h': h, 'server': server, 'receipt': receipt, 'unit': unit, 'get_unit': get_unit}
