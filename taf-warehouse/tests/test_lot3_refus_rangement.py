"""Lot 3 — refus de transfert et statut « en attente de rangement ».

Règles TAF (7 novembre 2026) :
- refus à l'arrivée : le magasinier rédige un rapport avec photo(s) et
  documents, le responsable magasin (Axel) le valide, l'exploitation est notifiée ;
- toute marchandise non rangée est « en attente de rangement » : aucune
  sortie ni aucun transfert avant rangement.
"""
import pytest
from helpers import signature, putaway, png_bytes


def driver(env):
    return env['c'].post('/api/drivers', headers=env['h']['mag'], json={'name': 'Chauffeur'}).json()['id']


def in_transit(env):
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt']()).json()['id']
    putaway(env['server'], u)
    tid = c.post('/api/transfers', headers=h['expl'], json={'unit_id': u, 'destination': 'Maritime'}).json()['id']
    assert c.post(f'/api/transfers/{tid}/approve', headers=h['expl2']).status_code == 200
    r = c.post(f'/api/transfers/{tid}/dispatch', headers=h['mag'], json={'confirmation': True, 'note': 'Camion AB-123-CD', 'driver_id': driver(env), 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True})
    assert r.status_code == 200, r.text
    return u, tid


def transfer(env, tid):
    return next(x for x in env['c'].get('/api/transfers', headers=env['h']['admin']).json() if x['id'] == tid)


def upload_photo(env, tid, who='mag_mar'):
    return env['c'].post(f'/api/documents/transfer/{tid}', headers=env['h'][who], files={'file': ('photo.png', png_bytes(), 'image/png')})


@pytest.fixture
def axel(env):
    """Axel, responsable magasin Maritime."""
    c, h = env['c'], env['h']
    from conftest import PWD
    assert c.post('/api/users', headers=h['admin'], json={'username': 'axel', 'password': PWD, 'role': 'manager', 'warehouses': ['Maritime']}).status_code == 200
    h['axel'] = {'Authorization': 'Bearer ' + c.post('/api/login', json={'username': 'axel', 'password': PWD}).json()['token']}
    return h['axel']


# --- Refus de transfert ---

def test_refusal_report_validated_by_warehouse_manager(env, axel):
    c, h = env['c'], env['h']
    u, tid = in_transit(env)
    r = c.post(f'/api/transfers/{tid}/refuse', headers=h['mag_mar'], json={'reason': 'Palette effondrée, colis écrasés et humides'})
    assert r.status_code == 200, r.text
    rid = r.json()['id']
    assert transfer(env, tid)['status'] == 'refusal_pending'
    assert env['get_unit'](u)['hold']
    assert upload_photo(env, tid).status_code == 200
    assert c.post(f'/api/documents/transfer/{tid}', headers=h['mag_mar'], files={'file': ('cmr.pdf', b'%PDF-1.4 lettre de voiture', 'application/pdf')}).status_code == 200
    assert c.post(f'/api/transfer-refusals/{rid}/review', headers=h['mag_mar'], json={'approve': True, 'note': 'Je valide'}).status_code == 403  # rôle
    v = c.post(f'/api/transfer-refusals/{rid}/review', headers=axel, json={'approve': True, 'note': 'Refus justifié, photos conformes'})
    assert v.status_code == 200, v.text
    assert transfer(env, tid)['status'] == 'refused'
    refusal = next(x for x in c.get('/api/transfer-refusals', headers=h['expl']).json() if x['id'] == rid)
    assert refusal['status'] == 'validated' and refusal['reviewed_by'] == 'axel' and refusal['report_document_id']
    pdf = c.get(f"/api/documents/{refusal['report_document_id']}/download", headers=h['expl'])
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    # L'exploitation des deux entrepôts est notifiée.
    for who in ('expl', 'expl_mar'):
        titles = [n['title'] for n in c.get('/api/notifications', headers=h[who]).json() if n['ref'] == tid]
        assert any('Refus de transfert validé' in t for t in titles), (who, titles)
    # Un transfert refusé ne peut plus être réceptionné.
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar']).status_code == 409


def test_refusal_requires_photo_and_independent_validator(env, axel):
    c, h = env['c'], env['h']
    _, tid = in_transit(env)
    assert c.post(f'/api/transfers/{tid}/refuse', headers=h['mag_mar'], json={'reason': 'court'}).status_code == 422
    rid = c.post(f'/api/transfers/{tid}/refuse', headers=axel, json={'reason': 'Colis ouverts à l’arrivée du camion'}).json()['id']
    assert c.post(f'/api/transfers/{tid}/refuse', headers=axel, json={'reason': 'Second rapport identique'}).status_code == 409
    assert c.post(f'/api/transfer-refusals/{rid}/review', headers=axel, json={'approve': True, 'note': 'Auto-validation'}).status_code == 403
    from conftest import PWD
    c.post('/api/users', headers=h['admin'], json={'username': 'resp_mar', 'password': PWD, 'role': 'manager', 'warehouses': ['Maritime']})
    other = {'Authorization': 'Bearer ' + c.post('/api/login', json={'username': 'resp_mar', 'password': PWD}).json()['token']}
    no_photo = c.post(f'/api/transfer-refusals/{rid}/review', headers=other, json={'approve': True, 'note': 'Refus justifié'})
    assert no_photo.status_code == 409 and 'photo' in no_photo.json()['detail'].lower()
    assert c.post(f'/api/transfer-refusals/{rid}/review', headers=h['resp'], json={'approve': True, 'note': 'Refus justifié'}).status_code == 403  # Afrique


def test_rejected_refusal_returns_transfer_to_transit(env, axel):
    c, h = env['c'], env['h']
    u, tid = in_transit(env)
    rid = c.post(f'/api/transfers/{tid}/refuse', headers=h['mag_mar'], json={'reason': 'Étiquettes illisibles sur deux colis'}).json()['id']
    r = c.post(f'/api/transfer-refusals/{rid}/review', headers=axel, json={'approve': False, 'note': 'Ré-étiqueter et réceptionner'})
    assert r.status_code == 200, r.text
    assert transfer(env, tid)['status'] == 'in_transit'
    assert c.post(f'/api/transfers/{tid}/receive', headers=h['mag_mar']).status_code == 200
    row = env['get_unit'](u)
    assert row['status'] == 'awaiting_putaway' and row['hold'], 'le blocage du refus reste à lever explicitement'


def test_transfer_documents_restricted_to_source_and_destination(env):
    c, h = env['c'], env['h']
    _, tid = in_transit(env)
    from conftest import PWD
    c.post('/api/users', headers=h['admin'], json={'username': 'mag_tms', 'password': PWD, 'role': 'worker', 'warehouses': ['TMS']})
    tms = {'Authorization': 'Bearer ' + c.post('/api/login', json={'username': 'mag_tms', 'password': PWD}).json()['token']}
    assert c.post(f'/api/documents/transfer/{tid}', headers=tms, files={'file': ('p.png', png_bytes(), 'image/png')}).status_code == 403
    assert upload_photo(env, tid).status_code == 200
    assert c.get('/api/documents', params={'kind': 'transfer', 'ref': tid}, headers=tms).status_code == 403
    docs = c.get('/api/documents', params={'kind': 'transfer', 'ref': tid}, headers=h['mag']).json()
    assert len(docs) == 1
    assert c.get(f"/api/documents/{docs[0]['id']}/download", headers=tms).status_code == 403


# --- En attente de rangement ---

def test_new_unit_awaits_putaway_and_cannot_leave(env):
    c, h = env['c'], env['h']
    u = env['unit'](env['receipt'](), placed=False).json()['id']
    assert env['get_unit'](u)['status'] == 'awaiting_putaway'
    assert c.post('/api/releases', headers=h['expl'], json={'unit_id': u, 'quantity': 1}).status_code == 400
    assert c.post('/api/transfers', headers=h['expl'], json={'unit_id': u, 'destination': 'Maritime'}).status_code == 400
    # Rangement réel via l'API sur un emplacement validé.
    assert c.put('/api/locations/AFR-R01-A1', headers=h['resp'], json={'capacity_kg': 1000, 'capacity_m3': 5, 'verified': True, 'notes': 'Plaque constructeur relevée'}).status_code == 200
    v = env['get_unit'](u)['version']
    assert c.post('/api/move', headers=h['mag'], json={'unit_id': u, 'destination': 'AFR-R01-A1', 'expected_version': v}).status_code == 200
    row = env['get_unit'](u)
    assert row['status'] == 'available' and row['location_id'] == 'AFR-R01-A1'
    assert c.post('/api/releases', headers=h['expl'], json={'unit_id': u, 'quantity': 1}).status_code == 200


def test_received_transfer_awaits_putaway(env):
    u, tid = in_transit(env)
    assert env['c'].post(f'/api/transfers/{tid}/receive', headers=env['h']['mag_mar']).status_code == 200
    row = env['get_unit'](u)
    assert row['warehouse'] == 'Maritime' and row['location_id'] is None and row['status'] == 'awaiting_putaway'


def test_migration_marks_unplaced_available_units(env):
    u = env['unit'](env['receipt'](), placed=False).json()['id']
    server = env['server']
    with server.db() as db:
        db.execute("UPDATE units SET status='available',location_id=NULL WHERE id=?", (u,))  # état V4.6
    server.init()
    assert env['get_unit'](u)['status'] == 'awaiting_putaway'


# --- Lot 4 : décision de l'exploitation après refus validé (option C) ---

def refused(env, axel):
    c, h = env['c'], env['h']
    u, tid = in_transit(env)
    rid = c.post(f'/api/transfers/{tid}/refuse', headers=h['mag_mar'], json={'reason': 'Palette effondrée, colis écrasés'}).json()['id']
    upload_photo(env, tid)
    assert c.post(f'/api/transfer-refusals/{rid}/review', headers=axel, json={'approve': True, 'note': 'Refus justifié'}).status_code == 200
    return u, tid


def test_refusal_decision_return_to_source(env, axel):
    c, h = env['c'], env['h']
    u, tid = refused(env, axel)
    body = {'decision': 'return', 'note': 'Retour Afrique pour reconditionnement'}
    for who in ('mag_mar', 'axel'):
        assert c.post(f'/api/transfers/{tid}/refusal-decision', headers=h[who], json=body).status_code == 403, who
    r = c.post(f'/api/transfers/{tid}/refusal-decision', headers=h['expl_mar'], json=body)
    assert r.status_code == 200, r.text
    back = r.json()['return_transfer_id']
    assert c.post(f'/api/transfers/{tid}/refusal-decision', headers=h['expl_mar'], json=body).status_code == 409
    assert transfer(env, tid)['status'] == 'returned'
    ret = transfer(env, back)
    assert (ret['source'], ret['destination'], ret['status'], ret['return_of']) == ('Maritime', 'Afrique', 'approved', tid)
    assert c.post(f'/api/transfers/{back}/cancel', headers=h['expl']).status_code == 409
    # Nouvelle signature du transporteur au départ de Maritime.
    r = c.post(f'/api/transfers/{back}/dispatch', headers=h['mag_mar'], json={'confirmation': True, 'note': 'Retour camion EF-456-GH', 'driver_id': driver(env), 'signature_name': 'Chauffeur retour', 'signature_data': signature(), 'signature_consent': True})
    assert r.status_code == 200, r.text
    assert c.post(f'/api/transfers/{back}/receive', headers=h['mag']).status_code == 200
    row = env['get_unit'](u)
    assert row['warehouse'] == 'Afrique' and row['status'] == 'awaiting_putaway' and row['hold']


def test_refusal_decision_accept_with_reserves(env, axel):
    c, h = env['c'], env['h']
    u, tid = refused(env, axel)
    assert c.post(f'/api/transfers/{tid}/refusal-decision', headers=h['expl_mar'], json={'decision': 'accept_with_reserves', 'note': 'x'}).status_code == 422
    r = c.post(f'/api/transfers/{tid}/refusal-decision', headers=h['expl_mar'], json={'decision': 'accept_with_reserves', 'note': 'Client accepte, réserves notifiées au transporteur'})
    assert r.status_code == 200, r.text
    t = transfer(env, tid)
    assert t['status'] == 'received_with_reserves' and t['received_by'] == 'expl_mar'
    row = env['get_unit'](u)
    assert row['warehouse'] == 'Maritime' and row['status'] == 'awaiting_putaway' and row['hold']
    assert c.get(f'/api/transfers/{tid}/dispatch-pdf', headers=h['expl']).status_code == 200


def test_refusal_decision_requires_validated_refusal(env, axel):
    c, h = env['c'], env['h']
    _, tid = in_transit(env)
    assert c.post(f'/api/transfers/{tid}/refusal-decision', headers=h['expl_mar'], json={'decision': 'return', 'note': 'Retour demandé'}).status_code == 409
