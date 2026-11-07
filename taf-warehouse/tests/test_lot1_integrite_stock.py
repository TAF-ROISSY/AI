"""Lot 1 — intégrité du stock.

Chaque test reproduit une anomalie relevée à l'audit de la V4.4 (A à E) et
fixe la règle métier validée par TAF :
- une unité peut être un colis ou une palette ;
- un blocage est levé par l'exploitation ou par un utilisateur explicitement
  habilité par le Super Admin (permission « lever les blocages ») ;
- le demandeur d'une sortie peut aussi l'autoriser.
"""
import base64, importlib, io, os, tempfile
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

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
        for name, role in [('expl', 'exploitation'), ('expl2', 'exploitation'), ('mag', 'worker'), ('resp', 'manager')]:
            r = c.post('/api/users', headers=admin, json={'username': name, 'password': PWD, 'role': role, 'warehouses': ['Afrique']})
            assert r.status_code == 200, r.text
        h = {'admin': admin, **{n: login(n) for n in ('expl', 'expl2', 'mag', 'resp')}}
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


def signature():
    img = Image.new('RGB', (400, 140), 'white')
    ImageDraw.Draw(img).line([(15, 90), (70, 45), (150, 100), (260, 30), (380, 85)], fill='black', width=5)
    bio = io.BytesIO(); img.save(bio, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(bio.getvalue()).decode()


# --- A. Création d'unités : anti-doublon et cohérence avec la réception ---

def test_A_unit_creation_replay_does_not_duplicate_stock(env):
    rec = env['receipt']()
    key = {'Idempotency-Key': 'unit-create-0001'}
    first = env['unit'](rec, headers=key)
    second = env['unit'](rec, headers=key)
    assert first.status_code == 200 and second.status_code == 200, (first.text, second.text)
    assert first.json()['id'] == second.json()['id']
    units = [u for u in env['c'].get('/api/units', headers=env['h']['admin']).json() if u['receipt_id'] == rec]
    assert len(units) == 1


def test_A_units_cannot_exceed_received_packages(env):
    rec = env['receipt'](expected=4, actual=4)
    assert env['unit'](rec, quantity=3).status_code == 200
    over = env['unit'](rec, quantity=2)
    assert over.status_code == 409, over.text
    assert env['unit'](rec, quantity=1).status_code == 200


def test_A_unit_type_colis_or_palette(env):
    rec = env['receipt']()
    r = env['unit'](rec, quantity=1, weight=20, unit_type='colis')
    assert r.status_code == 200, r.text
    assert env['get_unit'](r.json()['id'])['unit_type'] == 'colis'
    assert env['unit'](rec, quantity=2, weight=40, unit_type='colis').status_code == 400
    assert env['unit'](rec, quantity=1, weight=20, unit_type='conteneur').status_code == 422
    r = env['unit'](rec, quantity=2, weight=40)
    assert env['get_unit'](r.json()['id'])['unit_type'] == 'palette'


# --- B. Blocage conservatoire des unités d'une réception en écart ---

def test_B_unit_added_after_discrepancy_is_held(env):
    rec = env['receipt']()
    r = env['c'].post(f'/api/receipts/{rec}/discrepancy', headers=env['h']['mag'], json={'kind': 'damage', 'description': 'Palette éventrée'})
    assert r.status_code == 200, r.text
    u = env['unit'](rec).json()['id']
    assert env['get_unit'](u)['hold']


def test_B_receipt_with_quantity_gap_holds_its_units(env):
    rec = env['receipt'](expected=5, actual=4)
    u = env['unit'](rec).json()['id']
    assert env['get_unit'](u)['hold']


# --- C. Blocages multiples, levée tracée et habilitée ---

def test_C_holds_stack_and_are_lifted_one_by_one(env):
    c, h = env['c'], env['h']
    rec = env['receipt']()
    u = env['unit'](rec).json()['id']
    c.post(f'/api/receipts/{rec}/discrepancy', headers=h['mag'], json={'kind': 'missing', 'description': 'Un colis manquant'})
    r = c.post('/api/incidents', headers=h['mag'], json={'warehouse': 'Afrique', 'unit_id': u, 'category': 'damage', 'severity': 'major', 'description': 'Carton écrasé'})
    assert r.status_code == 200
    holds = c.get(f'/api/units/{u}/holds', headers=h['expl'])
    assert holds.status_code == 200, holds.text
    active = [x for x in holds.json() if not x['lifted_at']]
    assert {x['kind'] for x in active} == {'ecart_reception', 'incident'}
    first = active[0]['id']
    assert c.post(f'/api/holds/{first}/lift', headers=h['expl'], json={'reason': 'Contrôle effectué'}).status_code == 200
    assert env['get_unit'](u)['hold'], 'le second blocage doit rester actif'
    second = active[1]['id']
    assert c.post(f'/api/holds/{second}/lift', headers=h['expl'], json={'reason': 'Contrôle effectué'}).status_code == 200
    assert not env['get_unit'](u)['hold']
    history = c.get(f'/api/units/{u}/holds', headers=h['expl']).json()
    assert all(x['lifted_by'] == 'expl' and x['lift_reason'] for x in history)


def test_C_only_exploitation_or_granted_user_can_lift(env):
    c, h = env['c'], env['h']
    rec = env['receipt']()
    u = env['unit'](rec).json()['id']
    assert c.post(f'/api/units/{u}/hold', headers=h['resp'], json={'hold': 'Contrôle sûreté', 'reason': 'Doute sur le contenu'}).status_code == 200
    hold_id = c.get(f'/api/units/{u}/holds', headers=h['resp']).json()[0]['id']
    for who in ('resp', 'mag', 'admin'):
        assert c.post(f'/api/holds/{hold_id}/lift', headers=h[who], json={'reason': 'Levée'}).status_code == 403, who
    users = c.get('/api/users', headers=h['admin']).json()
    resp_id = next(x['id'] for x in users if x['username'] == 'resp')
    assert c.post(f'/api/users/{resp_id}/permissions', headers=h['expl'], json={'can_lift_holds': True}).status_code == 403
    assert c.post(f'/api/users/{resp_id}/permissions', headers=h['admin'], json={'can_lift_holds': True}).status_code == 200
    assert c.post(f'/api/holds/{hold_id}/lift', headers=h['resp'], json={'reason': 'Contrôle sûreté levé'}).status_code == 200
    assert not env['get_unit'](u)['hold']


def test_C_lift_requires_reason_and_cannot_be_repeated(env):
    c, h = env['c'], env['h']
    rec = env['receipt']()
    u = env['unit'](rec).json()['id']
    c.post(f'/api/units/{u}/hold', headers=h['expl'], json={'hold': 'Attente client', 'reason': 'Instruction client'})
    hold_id = c.get(f'/api/units/{u}/holds', headers=h['expl']).json()[0]['id']
    assert c.post(f'/api/holds/{hold_id}/lift', headers=h['expl'], json={'reason': ' '}).status_code == 422
    assert c.post(f'/api/holds/{hold_id}/lift', headers=h['expl'], json={'reason': 'Instruction reçue'}).status_code == 200
    assert c.post(f'/api/holds/{hold_id}/lift', headers=h['expl'], json={'reason': 'Instruction reçue'}).status_code == 409


# --- D. Sorties : rôles ---

def test_D_release_roles(env):
    c, h = env['c'], env['h']
    rec = env['receipt']()
    u = env['unit'](rec).json()['id']
    assert c.post('/api/releases', headers=h['mag'], json={'unit_id': u, 'quantity': 1}).status_code == 403
    out = c.post('/api/releases', headers=h['expl'], json={'unit_id': u, 'quantity': 1})
    assert out.status_code == 200, out.text
    rid = out.json()['id']
    # Règle TAF : le demandeur peut aussi autoriser.
    assert c.post(f'/api/releases/{rid}/authorize', headers=h['expl']).status_code == 200
    driver = c.post('/api/drivers', headers=h['mag'], json={'name': 'Chauffeur'}).json()['id']
    body = {'driver_id': driver, 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True}
    # La remise physique est faite par le magasin.
    assert c.post(f'/api/releases/{rid}/complete', headers=h['expl'], json=body).status_code == 403
    assert c.post(f'/api/releases/{rid}/complete', headers=h['mag'], json=body).status_code == 200


# --- E. Sortie partielle : le poids restant suit la quantité ---

def test_E_partial_release_updates_remaining_weight(env):
    c, h = env['c'], env['h']
    rec = env['receipt']()
    u = env['unit'](rec, quantity=4, weight=400).json()['id']
    rid = c.post('/api/releases', headers=h['expl'], json={'unit_id': u, 'quantity': 1}).json()['id']
    c.post(f'/api/releases/{rid}/authorize', headers=h['expl'])
    driver = c.post('/api/drivers', headers=h['mag'], json={'name': 'Chauffeur'}).json()['id']
    r = c.post(f'/api/releases/{rid}/complete', headers=h['mag'], json={'driver_id': driver, 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True})
    assert r.status_code == 200, r.text
    row = env['get_unit'](u)
    assert row['quantity'] == 3
    assert row['weight'] == pytest.approx(300)


# --- Migration : un blocage texte V4.4 devient un blocage tracé, sans perte ---

def test_legacy_v44_hold_is_migrated(env):
    rec = env['receipt']()
    u = env['unit'](rec).json()['id']
    server = env['server']
    with server.db() as c:
        c.execute("UPDATE units SET hold='Blocage douane manuel V4.4' WHERE id=?", (u,))
    server.init()  # redémarrage applicatif
    server.init()  # idempotent : pas de doublon
    holds = env['c'].get(f'/api/units/{u}/holds', headers=env['h']['expl']).json()
    assert [(x['kind'], x['reason']) for x in holds] == [('legacy', 'Blocage douane manuel V4.4')]
    assert env['c'].post(f"/api/holds/{holds[0]['id']}/lift", headers=env['h']['expl'], json={'reason': 'Mainlevée douane reçue'}).status_code == 200
    assert not env['get_unit'](u)['hold']
