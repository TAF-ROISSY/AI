import os,base64,pytest
@pytest.fixture(autouse=True)
def test_mfa_key(monkeypatch):
    monkeypatch.setenv("TAF_MFA_ENCRYPTION_KEY",base64.urlsafe_b64encode(b"test-only-key-for-warehouse-1234").decode())


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

        def unit(rec, quantity=4, weight=400, who='mag', headers=None, **extra):
            body = {'receipt_id': rec, 'description': 'Palette', 'quantity': quantity, 'weight': weight, 'volume': 1, 'dimensions_ok': True, **extra}
            return c.post('/api/units', headers={**h[who], **(headers or {})}, json=body)

        def get_unit(uid_):
            return next(x for x in c.get('/api/units', headers=admin).json() if x['id'] == uid_)

        yield {'c': c, 'h': h, 'server': server, 'receipt': receipt, 'unit': unit, 'get_unit': get_unit}
