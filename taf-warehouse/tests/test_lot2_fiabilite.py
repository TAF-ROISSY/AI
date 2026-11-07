"""Lot 2 — transactions, confidentialité des signatures, écarts de transfert.

Règle TAF (7 novembre 2026) : un blocage d'incident peut être levé alors
que l'incident est encore ouvert.
"""
import pytest
from helpers import signature


def driver(env):
    return env['c'].post('/api/drivers', headers=env['h']['mag'], json={'name': 'Chauffeur'}).json()['id']


def in_transit(env, quantity=4, weight=400):
    """Unité Afrique expédiée vers Maritime ; renvoie (unité, transfert)."""
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt'](), quantity=quantity, weight=weight).json()['id']
    t = c.post('/api/transfers', headers=h['expl'], json={'unit_id': u, 'destination': 'Maritime'})
    assert t.status_code == 200, t.text
    tid = t.json()['id']
    assert c.post(f'/api/transfers/{tid}/approve', headers=h['expl2']).status_code == 200
    r = c.post(f'/api/transfers/{tid}/dispatch', headers=h['mag'], json={'confirmation': True, 'note': 'Camion AB-123-CD', 'driver_id': driver(env), 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True})
    assert r.status_code == 200, r.text
    return u, tid


def transfer(env, tid):
    return next(x for x in env['c'].get('/api/transfers', headers=env['h']['admin']).json() if x['id'] == tid)


# --- Règle de levée des blocages d'incident ---

def test_incident_hold_can_be_lifted_while_incident_open(env):
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt']()).json()['id']
    inc = c.post('/api/incidents', headers=h['mag'], json={'warehouse': 'Afrique', 'unit_id': u, 'category': 'damage', 'severity': 'critical', 'description': 'Film déchiré'}).json()['id']
    hold = c.get(f'/api/units/{u}/holds', headers=h['expl']).json()[0]
    assert c.post(f"/api/holds/{hold['id']}/lift", headers=h['expl'], json={'reason': 'Refilmé, contrôle visuel OK'}).status_code == 200
    assert next(x for x in c.get('/api/incidents', headers=h['expl']).json() if x['id'] == inc)['status'] == 'open'
    assert not env['get_unit'](u)['hold']


# --- Signatures absentes des listes ---

def test_lists_do_not_expose_signatures(env):
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt']()).json()['id']
    rid = c.post('/api/releases', headers=h['expl'], json={'unit_id': u, 'quantity': 1}).json()['id']
    c.post(f'/api/releases/{rid}/authorize', headers=h['expl'])
    assert c.post(f'/api/releases/{rid}/complete', headers=h['mag'], json={'driver_id': driver(env), 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True}).status_code == 200
    row = next(x for x in c.get('/api/releases', headers=h['expl']).json() if x['id'] == rid)
    assert 'signature_data' not in row and row['has_signature'] == 1
    _, tid = in_transit(env)
    row = transfer(env, tid)
    assert 'signature_data' not in row and row['has_signature'] == 1
    # Les justificatifs PDF restent disponibles.
    assert c.get(f'/api/releases/{rid}/handover-pdf', headers=h['expl']).content.startswith(b'%PDF')
    assert c.get(f'/api/transfers/{tid}/dispatch-pdf', headers=h['expl']).content.startswith(b'%PDF')


# --- Réception de transfert : conforme ou avec écart ---

def test_transfer_receive_conform_without_body_stays_compatible(env):
    u, tid = in_transit(env)
    assert env['c'].post(f'/api/transfers/{tid}/receive', headers=env['h']['mag_mar']).status_code == 200
    assert transfer(env, tid)['status'] == 'received'
    row = env['get_unit'](u)
    assert row['warehouse'] == 'Maritime' and row['status'] == 'awaiting_putaway' and not row['hold']  # lot 3


def test_transfer_missing_package_is_held_until_independent_decision(env):
    c, h = env['c'], env['h']
    u, tid = in_transit(env, quantity=4, weight=400)
    r = c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar'], json={'observed_quantity': 3, 'condition': 'manquant', 'note': 'Un colis absent du camion'})
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'discrepancy'
    t = transfer(env, tid)
    assert t['status'] == 'discrepancy' and t['received_quantity'] == 3 and t['received_condition'] == 'manquant'
    row = env['get_unit'](u)
    # Jamais de correction silencieuse : la quantité reste celle expédiée jusqu'à décision.
    assert row['warehouse'] == 'Maritime' and row['quantity'] == 4 and row['hold']
    assert c.post('/api/releases', headers=h['expl_mar'], json={'unit_id': u, 'quantity': 1}).status_code == 400
    body = {'accept_observed': True, 'decision': 'Colis manquant confirmé par le transporteur'}
    assert c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['mag_mar'], json=body).status_code == 403  # pas de rôle
    assert c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['expl2'], json=body).status_code == 403  # entrepôt
    r = c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['expl_mar'], json=body)
    assert r.status_code == 200, r.text
    t = transfer(env, tid)
    assert t['status'] == 'received' and t['discrepancy_reviewed_by'] == 'expl_mar'
    row = env['get_unit'](u)
    assert row['quantity'] == 3 and row['weight'] == pytest.approx(300)
    assert row['hold'], 'la décision ne lève pas le blocage'
    moves = [m for m in c.get('/api/movements', headers=h['expl_mar']).json() if m['unit_id'] == u and m['kind'] == 'transfer_adjustment']
    assert len(moves) == 1 and moves[0]['quantity'] == -1
    assert c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['expl_mar'], json=body).status_code == 409


def test_transfer_receiver_cannot_decide_own_discrepancy(env):
    c, h = env['c'], env['h']
    u, tid = in_transit(env)
    # L'exploitation Maritime réceptionne elle-même : elle ne peut pas trancher.
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['expl_mar'], json={'observed_quantity': 4, 'condition': 'avarie', 'note': 'Palette écrasée'}).status_code == 200
    assert c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['expl_mar'], json={'accept_observed': True, 'decision': 'Avarie constatée'}).status_code == 403


def test_transfer_discrepancy_rejected_keeps_dispatched_quantity(env):
    c, h = env['c'], env['h']
    u, tid = in_transit(env, quantity=4)
    c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar'], json={'observed_quantity': 3, 'condition': 'conforme', 'note': 'Comptage rapide'})
    assert transfer(env, tid)['status'] == 'discrepancy'
    r = c.post(f'/api/transfers/{tid}/discrepancy-review', headers=h['expl_mar'], json={'accept_observed': False, 'decision': 'Recompté : 4 colis présents'})
    assert r.status_code == 200, r.text
    assert transfer(env, tid)['status'] == 'received'
    assert env['get_unit'](u)['quantity'] == 4


def test_transfer_receive_validation(env):
    c, h = env['c'], env['h']
    _, tid = in_transit(env)
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar'], json={'observed_quantity': 3, 'condition': 'manquant', 'note': ''}).status_code == 422
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar'], json={'observed_quantity': -1, 'condition': 'manquant', 'note': 'Test'}).status_code == 422
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar'], json={'observed_quantity': 4, 'condition': 'perdu', 'note': 'Test'}).status_code == 422


# --- Inventaire : le poids suit la quantité corrigée ---

def test_inventory_adjustment_updates_weight(env):
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt'](), quantity=4, weight=400).json()['id']
    with env['server'].db() as db:
        db.execute("UPDATE units SET location_id='AFR-TEMP' WHERE id=?", (u,))
    cid = c.post('/api/counts', headers=h['mag'], json={'unit_id': u, 'observed': 2}).json()['id']
    assert c.post(f'/api/counts/{cid}/recount', headers=h['expl2'], json={'observed': 2}).status_code == 200
    assert c.post(f'/api/counts/{cid}/review', headers=h['expl'], json={'approve': True, 'reason': 'Deux colis manquants confirmés'}).status_code == 200
    row = env['get_unit'](u)
    assert row['quantity'] == 2 and row['weight'] == pytest.approx(200)


# --- Anti-doublon sur la création de réception ---

def test_receipt_creation_replay_does_not_duplicate(env):
    c, h = env['c'], env['h']
    client_id = c.get('/api/clients', headers=h['mag']).json()[0]['id']
    body = {'warehouse': 'Afrique', 'client_id': client_id, 'expected': 2, 'actual': 2, 'weight': 50}
    key = {**h['mag'], 'Idempotency-Key': 'receipt-create-0001'}
    a = c.post('/api/receipts', headers=key, json=body).json()['id']
    b = c.post('/api/receipts', headers=key, json=body).json()['id']
    assert a == b and len(c.get('/api/receipts', headers=h['mag']).json()) == 1


# --- Atomicité : une erreur en cours d'opération ne laisse aucune trace partielle ---

def failing_audit(*args, **kwargs):
    raise RuntimeError('panne simulée après écriture')


@pytest.mark.parametrize('case', ['receipt', 'claim', 'incident_update', 'mission', 'document'])
def test_operations_are_atomic(env, monkeypatch, case):
    from fastapi.testclient import TestClient
    server, h = env['server'], env['h']
    c = env['c']
    client_id = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    inc = c.post('/api/incidents', headers=h['expl'], json={'warehouse': 'Afrique', 'category': 'damage', 'severity': 'minor', 'description': 'Test'}).json()['id']
    rec = env['receipt']()
    files_before = set((server.UPLOAD).iterdir())
    monkeypatch.setattr(server, 'audit', failing_audit)
    broken = TestClient(server.app, raise_server_exceptions=False)
    if case == 'receipt':
        r = broken.post('/api/receipts', headers=h['expl'], json={'warehouse': 'Afrique', 'client_id': client_id, 'expected': 1, 'actual': 1, 'weight': 1})
    elif case == 'claim':
        r = broken.post('/api/claims', headers=h['expl'], json={'warehouse': 'Afrique', 'description': 'Litige test'})
    elif case == 'incident_update':
        r = broken.post(f'/api/incidents/{inc}/update', headers=h['expl'], json={'status': 'investigating'})
    elif case == 'mission':
        r = broken.post('/api/missions', headers=h['expl'], json={'warehouse': 'Afrique', 'title': 'Mission test'})
    else:
        r = broken.post(f'/api/documents/receipt/{rec}', headers=h['expl'], files={'file': ('bl.pdf', b'%PDF-1.4 test', 'application/pdf')})
    assert r.status_code == 500
    monkeypatch.undo()
    with server.db() as db:
        assert db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
        assert db.execute('SELECT status FROM incidents WHERE id=?', (inc,)).fetchone()[0] == 'open'
        assert db.execute('SELECT COUNT(*) FROM missions').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 0
    assert set(server.UPLOAD.iterdir()) == files_before, 'aucun fichier orphelin'
