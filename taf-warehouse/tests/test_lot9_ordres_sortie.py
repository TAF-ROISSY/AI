"""Lot 9 — ordres de sortie multi-unités : réservation, préparation/contrôle, autorisation,
remise signée (totale ou partielle), refus de signature, annulation du reliquat, bon de remise."""
import io
import pytest
from pypdf import PdfReader
from helpers import signature


def units(env, n=3, quantity=4, weight=400):
    rec = env['receipt'](expected=quantity * n, actual=quantity * n)
    return [env['unit'](rec, quantity=quantity, weight=weight).json()['id'] for _ in range(n)]


def order(env, lines, who='expl', ref='DOS-4521'):
    return env['c'].post('/api/release-orders', headers=env['h'][who], json={'warehouse': 'Afrique', 'reference': ref, 'lines': lines})


def get_order(env, oid):
    return next(o for o in env['c'].get('/api/release-orders', headers=env['h']['expl']).json() if o['id'] == oid)


def driver(env):
    return env['c'].post('/api/drivers', headers=env['h']['mag'], json={'name': 'Chauffeur', 'company': 'Transports Dupont', 'plate': 'AB-123-CD'}).json()['id']


def sign(env, extra=None):
    return {'driver_id': driver(env), 'signature_name': 'Jean Martin', 'signature_data': signature(), 'signature_consent': True, **(extra or {})}


def prepare_all(env, oid, ids):
    for u in ids:
        r = env['c'].post(f'/api/release-orders/{oid}/prepare', headers=env['h']['mag'], json={'unit_id': u, 'note': 'Contrôlé, étiquette lisible'})
        assert r.status_code == 200, r.text


def test_full_cycle_reserves_prepares_authorizes_and_hands_over(env):
    c, h = env['c'], env['h']
    ids = units(env)
    r = order(env, [{'unit_id': ids[0], 'quantity': 4}, {'unit_id': ids[1], 'quantity': 2}, {'unit_id': ids[2], 'quantity': 4}])
    assert r.status_code == 200, r.text
    oid = r.json()['id']
    o = get_order(env, oid)
    assert o['status'] == 'requested' and len(o['lines']) == 3
    # Stock réservé : une autre demande sur la même quantité est refusée.
    assert c.post('/api/releases', headers=h['expl'], json={'unit_id': ids[0], 'quantity': 1}).status_code == 400
    # Autorisation impossible avant préparation complète.
    assert c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl']).status_code == 409
    assert c.post(f'/api/release-orders/{oid}/prepare', headers=h['expl'], json={'unit_id': ids[0], 'note': 'x controle'}).status_code == 403  # rôle magasin
    prepare_all(env, oid, ids)
    assert get_order(env, oid)['status'] == 'prepared'
    assert c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl']).status_code == 200
    assert c.post(f'/api/release-orders/{oid}/complete', headers=h['expl'], json=sign(env)).status_code == 403  # remise par le magasin
    r = c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env))
    assert r.status_code == 200, r.text
    o = get_order(env, oid)
    assert o['status'] == 'completed' and len(o['handovers']) == 1
    stock = {u['id']: u for u in c.get('/api/units', headers=h['admin']).json()}
    assert stock[ids[0]]['status'] == 'exited' and stock[ids[0]]['quantity'] == 0
    assert stock[ids[1]]['quantity'] == 2 and stock[ids[1]]['weight'] == pytest.approx(200)
    pdf = c.get(f"/api/release-orders/{oid}/handovers/{o['handovers'][0]['id']}/pdf", headers=h['expl'])
    assert pdf.status_code == 200
    text = ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    for expected in ('BON DE REMISE', oid, 'DOS-4521', 'Jean Martin', 'AB-123-CD', ids[0], ids[2]):
        assert expected.lower() in text.lower(), expected
    # Remise unique : rejouer ne sort pas deux fois.
    assert c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env)).status_code == 409


def test_partial_handover_keeps_identified_remainder(env):
    c, h = env['c'], env['h']
    ids = units(env)
    oid = order(env, [{'unit_id': u, 'quantity': 4} for u in ids]).json()['id']
    prepare_all(env, oid, ids)
    c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
    r = c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env, {'unit_ids': ids[:2]}))
    assert r.status_code == 200, r.text
    o = get_order(env, oid)
    assert o['status'] == 'partial'
    assert [l['status'] for l in sorted(o['lines'], key=lambda l: ids.index(l['unit_id']))] == ['completed', 'completed', 'authorized']
    stock = {u['id']: u for u in c.get('/api/units', headers=h['admin']).json()}
    assert stock[ids[2]]['quantity'] == 4 and stock[ids[2]]['status'] == 'available'  # reliquat intact
    # Le reliquat part plus tard, avec sa propre signature.
    assert c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env)).status_code == 200
    o = get_order(env, oid)
    assert o['status'] == 'completed' and len(o['handovers']) == 2


def test_cancel_remainder_releases_reservation(env):
    c, h = env['c'], env['h']
    ids = units(env)
    oid = order(env, [{'unit_id': u, 'quantity': 4} for u in ids]).json()['id']
    prepare_all(env, oid, ids)
    c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
    c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env, {'unit_ids': ids[:1]}))
    assert c.post(f'/api/release-orders/{oid}/cancel', headers=h['mag'], json={'reason': 'Client annule le reste'}).status_code == 403
    assert c.post(f'/api/release-orders/{oid}/cancel', headers=h['expl'], json={'reason': 'x'}).status_code == 422
    assert c.post(f'/api/release-orders/{oid}/cancel', headers=h['expl'], json={'reason': 'Client annule le reliquat'}).status_code == 200
    o = get_order(env, oid)
    assert o['status'] == 'closed_partial'
    assert c.post('/api/releases', headers=h['expl'], json={'unit_id': ids[2], 'quantity': 4}).status_code == 200  # réservation libérée


def test_signature_refusal_is_recorded_without_stock_change(env):
    c, h = env['c'], env['h']
    ids = units(env, n=1)
    oid = order(env, [{'unit_id': ids[0], 'quantity': 4}]).json()['id']
    prepare_all(env, oid, ids)
    c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
    r = c.post(f'/api/release-orders/{oid}/refuse-signature', headers=h['mag'], json={'driver_id': driver(env), 'reason': 'Le chauffeur conteste l’état d’une palette'})
    assert r.status_code == 200, r.text
    o = get_order(env, oid)
    assert o['status'] == 'authorized' and o['refusals'][0]['reason'].startswith('Le chauffeur')
    assert next(u for u in c.get('/api/units', headers=h['admin']).json() if u['id'] == ids[0])['quantity'] == 4
    assert any('Refus de signature' in n['title'] for n in c.get('/api/notifications', headers=h['expl']).json())


def test_validation_rules(env):
    c, h = env['c'], env['h']
    ids = units(env, n=2)
    assert order(env, [{'unit_id': ids[0], 'quantity': 4}], who='mag').status_code == 403
    assert order(env, []).status_code == 422
    assert order(env, [{'unit_id': ids[0], 'quantity': 4}, {'unit_id': ids[0], 'quantity': 1}]).status_code == 400  # doublon
    assert order(env, [{'unit_id': ids[0], 'quantity': 5}]).status_code == 400  # au-delà du stock
    c.post(f'/api/units/{ids[1]}/hold', headers=h['expl'], json={'hold': 'Douane', 'reason': 'Attente mainlevée'})
    assert order(env, [{'unit_id': ids[1], 'quantity': 1}]).status_code == 400  # unité bloquée : rien n'est réservé
    assert c.post('/api/releases', headers=h['expl'], json={'unit_id': ids[0], 'quantity': 4}).status_code == 200


def test_hold_after_authorization_blocks_handover(env):
    c, h = env['c'], env['h']
    ids = units(env, n=1)
    oid = order(env, [{'unit_id': ids[0], 'quantity': 4}]).json()['id']
    prepare_all(env, oid, ids)
    c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
    c.post('/api/incidents', headers=h['mag'], json={'warehouse': 'Afrique', 'unit_id': ids[0], 'category': 'damage', 'severity': 'major', 'description': 'Palette percée au chargement'})
    assert c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json=sign(env)).status_code == 400


def test_order_lines_cannot_be_driven_by_legacy_release_routes(env):
    c, h = env['c'], env['h']
    ids = units(env, n=1)
    oid = order(env, [{'unit_id': ids[0], 'quantity': 4}]).json()['id']
    line = get_order(env, oid)['lines'][0]['id']
    assert c.post(f'/api/releases/{line}/authorize', headers=h['expl']).status_code == 409
    assert c.post(f'/api/releases/{line}/cancel', headers=h['expl']).status_code == 409


def test_order_creation_is_idempotent(env):
    c, h = env['c'], env['h']
    ids = units(env, n=1)
    body = {'warehouse': 'Afrique', 'reference': 'DOS-1', 'lines': [{'unit_id': ids[0], 'quantity': 4}]}
    key = {**h['expl'], 'Idempotency-Key': 'ordre-sortie-0001'}
    ra = c.post('/api/release-orders', headers=key, json=body)
    rb = c.post('/api/release-orders', headers=key, json=body)
    assert ra.status_code == rb.status_code == 200 and ra.json()['id'].startswith('ORD-')
    assert ra.json() == rb.json()
    orders = c.get('/api/release-orders', headers=h['expl']).json()
    assert isinstance(orders, list) and len(orders) == 1 and len(orders[0]['lines']) == 1
