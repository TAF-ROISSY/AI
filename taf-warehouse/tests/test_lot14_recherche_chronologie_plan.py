"""Recherche universelle, chronologie d'une unité, plan des racks."""
from helpers import signature, putaway


def setup(env):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]
    pk = [{'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 150, 'weight_kg': 300, 'packages': 3}]
    rec = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl['id'], 'awb': '057-99887766', 'expected': 3, 'actual': 3, 'weight': 300, 'packages': pk}).json()
    unit = rec['units'][0]
    c.get(f'/api/labels/{unit}', headers=h['mag'])
    putaway(env['server'], unit)
    c.post(f'/api/units/{unit}/hold', headers=h['expl'], json={'hold': 'Contrôle douane', 'reason': 'Vérification documentaire'})
    hold = c.get(f'/api/units/{unit}/holds', headers=h['expl']).json()[0]['id']
    c.post(f'/api/holds/{hold}/lift', headers=h['expl'], json={'reason': 'Mainlevée reçue'})
    d = c.post('/api/drivers', headers=h['mag'], json={'name': 'Ali Diallo', 'company': 'Trans Sahel', 'plate': 'EF-456-GH'}).json()['id']
    oid = c.post('/api/release-orders', headers=h['expl'], json={'warehouse': 'Afrique', 'reference': 'DOS-7788', 'lines': [{'unit_id': unit, 'quantity': 1}]}).json()['id']
    c.post(f'/api/release-orders/{oid}/prepare', headers=h['mag'], json={'unit_id': unit, 'note': 'Contrôlé'})
    c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
    assert c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json={'driver_id': d, 'signature_name': 'Ali Diallo', 'signature_data': signature(), 'signature_consent': True}).status_code == 200
    return rec['id'], unit, oid, cl


def test_universal_search(env):
    rec, unit, oid, cl = setup(env)
    c, h = env['c'], env['h']
    def s(q, who='expl'):
        r = c.get('/api/search', params={'q': q}, headers=h[who]); assert r.status_code == 200, r.text; return r.json()
    assert [x['id'] for x in s('99887766')['receipts']] == [rec]          # LTA
    assert unit in [x['id'] for x in s(unit[-6:].lower())['units']]       # unité, sans casse
    assert [x['id'] for x in s('DOS-7788')['release_orders']] == [oid]    # référence de sortie
    assert [x['name'] for x in s('diallo')['drivers']] == ['Ali Diallo']
    assert [x['id'] for x in s('AFR-TEMP')['locations']] == ['AFR-TEMP']
    assert s(cl['name'][:6])['clients']
    assert s('a')['total'] == 0                                           # 2 caractères minimum
    assert s('99887766', who='expl_mar')['total'] == 0                    # cloisonnement entrepôt


def test_unit_timeline(env):
    rec, unit, oid, _ = setup(env)
    r = env['c'].get(f'/api/units/{unit}/timeline', headers=env['h']['expl'])
    assert r.status_code == 200, r.text
    events = r.json()['events']
    kinds = [e['kind'] for e in events]
    for expected in ('reception', 'label', 'hold', 'hold_lift', 'release_order', 'prepare', 'exit'):
        assert expected in kinds, (expected, kinds)
    assert kinds.index('reception') < kinds.index('hold') < kinds.index('hold_lift') < kinds.index('exit')
    assert [e['at'] for e in events] == sorted(e['at'] for e in events)
    exit_ev = next(e for e in events if e['kind'] == 'exit')
    assert 'Ali Diallo' in exit_ev['detail'] and exit_ev['actor'] == 'mag'
    assert env['c'].get(f'/api/units/{unit}/timeline', headers=env['h']['expl_mar']).status_code == 403


def test_rack_plan(env):
    rec, unit, oid, _ = setup(env)
    c, h = env['c'], env['h']
    c.put('/api/locations/AFR-R01-A1', headers=h['resp'], json={'capacity_kg': 1000, 'capacity_m3': 5, 'verified': True, 'notes': 'Plaque constructeur relevée'})
    c.put('/api/locations/AFR-R01-A2', headers=h['resp'], json={'capacity_kg': 1000, 'capacity_m3': 5, 'verified': True, 'blocked': True, 'notes': 'Validation : lisse endommagée'})
    r = c.get('/api/locations/plan', params={'warehouse': 'Afrique'}, headers=h['mag'])
    assert r.status_code == 200, r.text
    plan = r.json()
    racks = {x['rack']: x for x in plan['racks']}
    assert set(racks) >= {'R01', 'R02', 'TEMP'}
    cells = {cell['id']: cell for rack in plan['racks'] for lvl in rack['levels'] for cell in lvl['cells']}
    assert cells['AFR-R01-A1']['state'] == 'free' and cells['AFR-R01-A2']['state'] == 'blocked'
    assert cells['AFR-R01-B3']['state'] == 'unverified'
    assert cells['AFR-TEMP']['units'] == 1 and cells['AFR-TEMP']['kg'] == 200
    assert [lvl['level'] for lvl in racks['R01']['levels']] == ['C', 'B', 'A']   # du haut vers le bas
    assert c.get('/api/locations/plan', params={'warehouse': 'Maritime'}, headers=h['mag']).status_code == 403



def test_discrepancies_screen_endpoint_exists(env):
    """L'écran « Écarts de réception » appelait /api/discrepancies, qui n'existait pas (404)."""
    rec = env['receipt']()
    env['c'].post(f'/api/receipts/{rec}/discrepancy', headers=env['h']['mag'], json={'kind': 'missing', 'description': 'Un colis manquant'})
    r = env['c'].get('/api/discrepancies', headers=env['h']['expl'])
    assert r.status_code == 200 and len(r.json()) == 1
