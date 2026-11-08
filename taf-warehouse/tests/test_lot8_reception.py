"""Lot 8 — réception complète : colisage par unité, totaux, incohérences, sûreté, étiquettes."""
import io
import pytest
from pypdf import PdfReader


def receipt(env, packages, who='mag', **over):
    c, h = env['c'], env['h']
    client_id = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    body = {'warehouse': 'Afrique', 'client_id': client_id, 'awb': '057-12345675', 'expected': 6, 'actual': 6, 'weight': 650,
            'shipper': 'SOCIETE EXPEDITRICE', 'carrier': 'Transports Dupont', 'transport_ref': 'CMR-2026-001',
            'folder_ref': 'DOS-4521', 'nature': 'Pièces détachées', 'apparent_condition': 'conforme',
            'security_status': 'securise', 'packages': packages}
    body.update(over)
    return c.post('/api/receipts', headers=h[who], json=body)


PALETTES = [
    {'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 150, 'weight_kg': 300, 'packages': 3},
    {'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 100, 'weight_kg': 250, 'packages': 2},
    {'kind': 'colis', 'length_cm': 60, 'width_cm': 40, 'height_cm': 40, 'weight_kg': 100, 'packages': 1, 'notes': 'Carton fragile'},
]


def units_of(env, rid):
    return sorted([u for u in env['c'].get('/api/units', headers=env['h']['admin']).json() if u['receipt_id'] == rid], key=lambda u: u['unit_index'])


def test_packing_list_creates_numbered_units_and_totals(env):
    r = receipt(env, PALETTES)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['status'] == 'received' and data['warnings'] == []
    t = data['totals']
    assert t['units'] == 3 and t['packages'] == 6 and t['weight_kg'] == pytest.approx(650)
    assert t['volume_m3'] == pytest.approx(1.44 + 0.96 + 0.096)
    assert t['volumetric_weight_kg'] == pytest.approx((1.44 + 0.96 + 0.096) * 1000 / 6, rel=1e-3)  # IATA 1:6000
    us = units_of(env, data['id'])
    assert [(u['unit_index'], u['unit_count'], u['unit_type'], u['quantity']) for u in us] == [(1, 3, 'palette', 3), (2, 3, 'palette', 2), (3, 3, 'colis', 1)]
    assert us[0]['length_cm'] == 120 and us[0]['volume'] == pytest.approx(1.44) and us[0]['dimensions_ok'] == 1
    assert all(u['status'] == 'awaiting_putaway' and not u['hold'] for u in us)
    rec = next(x for x in env['c'].get('/api/receipts', headers=env['h']['admin']).json() if x['id'] == data['id'])
    assert rec['shipper'] == 'SOCIETE EXPEDITRICE' and rec['security_status'] == 'securise' and rec['volumetric_weight'] == pytest.approx(t['volumetric_weight_kg'])


def test_inconsistencies_are_reported_and_held(env):
    # 6 colis annoncés reçus, mais la liste n'en décrit que 5 ; poids déclaré très différent.
    r = receipt(env, PALETTES[:2] + [{'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 100, 'weight_kg': 10, 'packages': 0}], weight=900)
    assert r.status_code == 422  # une unité contient au moins un colis
    r = receipt(env, PALETTES[:2], weight=900)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['status'] == 'discrepancy'
    joined = ' '.join(data['warnings'])
    assert 'colis' in joined and 'poids' in joined.lower()
    us = units_of(env, data['id'])
    assert len(us) == 2 and all(u['hold'] for u in us)


def test_expected_vs_actual_gap_still_detected(env):
    r = receipt(env, PALETTES, expected=8)
    assert r.json()['status'] == 'discrepancy'
    us = units_of(env, r.json()['id'])
    assert len(us) == 3 and all(u['hold'] for u in us)


@pytest.mark.parametrize('field,value,kind', [('security_status', 'non_securise', 'surete'), ('security_status', 'a_controler', 'surete'), ('apparent_condition', 'endommage', 'avarie')])
def test_security_or_damage_blocks_units(env, field, value, kind):
    r = receipt(env, PALETTES, **{field: value})
    assert r.status_code == 200, r.text
    us = units_of(env, r.json()['id'])
    assert len(us) == 3
    for u in us:
        holds = env['c'].get(f"/api/units/{u['id']}/holds", headers=env['h']['expl']).json()
        assert kind in {x['kind'] for x in holds if not x['lifted_at']}


def test_invalid_values_rejected(env):
    assert receipt(env, PALETTES, security_status='peut-etre').status_code == 422
    bad = [dict(PALETTES[0], height_cm=-1)]
    assert receipt(env, bad).status_code == 422
    assert receipt(env, [dict(PALETTES[2], packages=2)]).status_code == 400  # un colis = 1 colis


def test_packing_list_receipt_is_idempotent(env):
    c, h = env['c'], env['h']
    key = {'Idempotency-Key': 'reception-colisage-0001'}
    client_id = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    body = {'warehouse': 'Afrique', 'client_id': client_id, 'expected': 6, 'actual': 6, 'weight': 650, 'packages': PALETTES}
    a = c.post('/api/receipts', headers={**h['mag'], **key}, json=body).json()
    b = c.post('/api/receipts', headers={**h['mag'], **key}, json=body).json()
    assert a == b and len(units_of(env, a['id'])) == 3


def test_legacy_receipt_without_packing_list_unchanged(env):
    r = env['receipt']()
    assert units_of(env, r) == []


def test_label_shows_receipt_client_awb_and_numbering(env):
    data = receipt(env, PALETTES).json()
    second = units_of(env, data['id'])[1]
    pdf = env['c'].get(f"/api/labels/{second['id']}", headers=env['h']['mag'])
    assert pdf.status_code == 200
    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    for expected in ('2/3', data['id'], '057-12345675', 'CLIENT', 'Afrique', '250', second['id']):
        assert expected in text, (expected, text)


def test_label_prints_are_recorded_without_creating_units(env):
    c, h = env['c'], env['h']
    data = receipt(env, PALETTES).json()
    ids = [u['id'] for u in units_of(env, data['id'])]
    c.get(f'/api/labels/{ids[0]}', headers=h['mag'])
    c.get(f'/api/labels/{ids[0]}', headers=h['mag'])
    c.get('/api/labels-batch', params={'ids': ','.join(ids)}, headers=h['mag'])
    hist = c.get(f'/api/labels/{ids[0]}/history', headers=h['mag']).json()
    assert len(hist) == 3 and all(x['actor'] == 'mag' for x in hist)
    assert [x['reprint'] for x in hist] == [0, 1, 1]
    assert len(units_of(env, data['id'])) == 3
