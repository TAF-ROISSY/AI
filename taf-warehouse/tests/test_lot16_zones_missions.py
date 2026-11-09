"""Lot 15 : générateur de zones de stockage, n° d'entrée E-000001, demandes au magasin depuis la fiche, prise en charge, historique."""
import io
from pypdf import PdfReader
from helpers import putaway


def pdf_text(raw):
    return ' '.join(' '.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages).split())


def gen(env, who='resp', **body):
    return env['c'].post('/api/locations/generate', headers=env['h'][who], json={'warehouse': 'Afrique', **body})


def test_rack_generator_numbering_and_preview(env):
    r = gen(env, kind='rack', names=['G', 'D'], levels=3, positions=8, dry_run=True)
    assert r.status_code == 200, r.text
    assert r.json()['total'] == 48 and r.json()['new'] == 48 and r.json()['sample'][0] == 'AFR-G-1-01'
    assert env['c'].get('/api/locations', headers=env['h']['mag'], params={'warehouse': 'Afrique'}).json()[0]['id'] != 'AFR-G-1-01'  # aperçu : rien créé
    r = gen(env, kind='rack', names=['g', 'd'], levels=3, positions=8, capacity_kg=1000, capacity_m3=2.5, proof='Plaque constructeur relevée')
    assert r.status_code == 200 and r.json()['created'] == 48
    ids = {l['id']: l for l in env['c'].get('/api/locations', headers=env['h']['mag'], params={'warehouse': 'Afrique'}).json()}
    assert {'AFR-G-1-01', 'AFR-G-3-08', 'AFR-D-2-05'} <= set(ids) and ids['AFR-G-2-05']['verified'] == 1 and ids['AFR-G-2-05']['zone'] == 'Rack gauche · étage 2'
    assert gen(env, kind='rack', names=['G'], levels=3, positions=8).status_code == 409             # déjà existants
    r = gen(env, kind='rack', names=['G'], levels=3, positions=10)                                   # extension : seulement les nouveaux
    assert r.json()['created'] == 6 and r.json()['skipped'] == 24
    plan = env['c'].get('/api/locations/plan', headers=env['h']['mag'], params={'warehouse': 'Afrique'}).json()
    g = next(x for x in plan['racks'] if x['rack'] == 'G')
    assert g['kind'] == 'rack' and g['label'] == 'Rack gauche' and [lv['level'] for lv in g['levels']] == ['3', '2', '1']
    assert [c['id'] for c in g['levels'][2]['cells']][:2] == ['AFR-G-1-01', 'AFR-G-1-02']


def test_floor_shelves_vault(env):
    assert gen(env, kind='floor', names=['A', 'B'], positions=12).json()['created'] == 24
    assert gen(env, kind='shelf', count=3, levels=4, positions=5).json()['created'] == 60
    assert gen(env, kind='vault', positions=1).json()['created'] == 1
    ids = {l['id'] for l in env['c'].get('/api/locations', headers=env['h']['mag'], params={'warehouse': 'Afrique'}).json()}
    assert {'AFR-SOL-A-01', 'AFR-SOL-B-12', 'AFR-ET1-1-01', 'AFR-ET3-4-05', 'AFR-COFFRE'} <= ids
    r = env['c'].post('/api/locations/generate', headers=env['h']['admin'], json={'warehouse': 'TMS', 'kind': 'vault', 'positions': 4})
    assert r.json()['ids'] == ['TMS-COFFRE-01', 'TMS-COFFRE-02', 'TMS-COFFRE-03', 'TMS-COFFRE-04']
    plan = env['c'].get('/api/locations/plan', headers=env['h']['mag'], params={'warehouse': 'Afrique'}).json()
    kinds = [x['kind'] for x in plan['racks']]
    assert kinds.index('rack') < kinds.index('shelf') < kinds.index('floor') < kinds.index('vault') < kinds.index('temp')
    sol = next(x for x in plan['racks'] if x['kind'] == 'floor')
    assert [lv['level'] for lv in sol['levels']] == ['A', 'B']
    pdf = env['c'].get('/api/locations/labels', headers=env['h']['mag'], params={'warehouse': 'Afrique', 'structure': 'SOL'})
    assert pdf.status_code == 200 and len(PdfReader(io.BytesIO(pdf.content)).pages) == 4 and 'AFR-SOL-A-01' in pdf_text(pdf.content)


def test_generator_rules_and_structure_removal(env):
    assert gen(env, who='mag', kind='rack', names=['G'], levels=1, positions=2).status_code == 403
    assert gen(env, who='expl_mar', kind='rack', names=['G'], levels=1, positions=2).status_code == 403
    assert gen(env, kind='rack', names=[], levels=1, positions=2).status_code == 400
    assert gen(env, kind='rack', names=['GAUCHE'], levels=1, positions=2).status_code == 400
    assert gen(env, kind='rack', names=['G'], levels=1, positions=2, proof='Plaque relevée').status_code == 400  # preuve sans capacité
    gen(env, kind='rack', names=['G'], levels=1, positions=2, capacity_kg=800, capacity_m3=2, proof='Plaque constructeur')
    c, h = env['c'], env['h']
    rec = env['receipt']()
    unit = env['unit'](rec, placed=False).json()['id']
    putaway(env['server'], unit, 'AFR-G-1-01')
    body = {'warehouse': 'Afrique', 'structure': 'G', 'reason': 'Rack démonté'}
    assert c.post('/api/locations/remove-structure', headers=h['resp'], json=body).status_code == 409   # occupé
    with env['server'].db() as db:
        db.execute("UPDATE units SET status='exited',location_id=NULL WHERE id=?", (unit,))
        db.execute("INSERT INTO movements(id,at,actor,unit_id,kind,source,destination,quantity,reference) VALUES('MV-T','2026-01-01T00:00:00+00:00','mag',?,'move','AFR-TEMP','AFR-G-1-01',4,'test')", (unit,))
    r = c.post('/api/locations/remove-structure', headers=h['resp'], json=body)
    assert r.status_code == 200 and r.json() == {'removed': 2, 'archived': 1}
    ids = {l['id'] for l in c.get('/api/locations', headers=h['mag'], params={'warehouse': 'Afrique'}).json()}
    assert 'AFR-G-1-01' not in ids and 'AFR-G-1-02' not in ids
    assert gen(env, kind='rack', names=['G'], levels=1, positions=2).json() == {'created': 1, 'reactivated': 1, 'skipped': 0, 'ids': ['AFR-G-1-02', 'AFR-G-1-01']}


def test_receipt_numbers_are_sequential(env):
    ids = [env['receipt']() for _ in range(3)]
    assert ids == ['E-000001', 'E-000002', 'E-000003']
    r = env['c'].post('/api/receipts', headers=env['h']['mag_mar'], json={'warehouse': 'Maritime', 'client_id': env['c'].get('/api/clients', headers=env['h']['admin']).json()[0]['id'], 'expected': 1, 'actual': 1, 'weight': 10})
    assert r.json()['id'] == 'E-000004'                                               # compteur unique tous entrepôts


def stocked_receipt(env):
    rec = env['receipt'](expected=8, actual=8)
    units = [env['unit'](rec, quantity=4, weight=200).json()['id'] for _ in range(2)]
    return rec, units


def test_preparation_request_take_complete_and_pdf(env):
    c, h = env['c'], env['h']
    rec, units = stocked_receipt(env)
    assert c.post(f'/api/receipts/{rec}/missions', headers=h['mag'], json={}).status_code == 403
    r = c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'description': 'Filmer la palette, enlèvement 14 h', 'priority': 'urgent'})
    assert r.status_code == 200 and r.json()['status'] == 'to_assign'
    mid = r.json()['id']
    feed = c.get('/api/missions/feed', headers=h['mag']).json()
    assert feed['count'] == 1 and feed['missions'][0]['id'] == mid and feed['missions'][0]['receipt_id'] == rec
    assert c.get('/api/missions/feed', headers=h['mag_mar']).json()['count'] == 0       # autre entrepôt
    assert any(n['ref'] == mid for n in c.get('/api/notifications', headers=h['mag']).json())
    assert c.post(f'/api/missions/{mid}/status', headers=h['mag_mar'], json={'action': 'take'}).status_code == 403
    assert c.post(f'/api/missions/{mid}/status', headers=h['mag'], json={'action': 'take'}).status_code == 200
    m = next(x for x in c.get('/api/missions', headers=h['expl']).json() if x['id'] == mid)
    assert m['status'] == 'in_progress' and m['assignee'] == 'mag' and m['started_at']
    assert c.post(f'/api/missions/{mid}/status', headers=h['expl2'], json={'action': 'take'}).status_code == 409   # déjà prise
    assert c.get('/api/missions/feed', headers=h['mag']).json()['count'] == 0
    r = c.post(f'/api/missions/{mid}/status', headers=h['mag'], json={'action': 'complete', 'note': 'Palettes filmées et prêtes quai 2'})
    assert r.status_code == 409 and '2 unité(s) restant' in r.text                      # chaque unité doit être scannée
    assert c.post(f'/api/missions/{mid}/check', headers=h['mag'], json={'unit_id': 'UNIT-INCONNUE'}).status_code == 400
    assert c.post(f'/api/missions/{mid}/check', headers=h['expl2'], json={'unit_id': units[0]}).status_code == 403
    assert c.post(f'/api/missions/{mid}/check', headers=h['mag'], json={'unit_id': 'TAF:UNIT:' + units[0]}).json() == {'ok': True, 'checked': 1, 'total': 2}
    assert c.post(f'/api/missions/{mid}/check', headers=h['mag'], json={'unit_id': units[0]}).status_code == 409
    m = next(x for x in c.get('/api/missions', headers=h['mag']).json() if x['id'] == mid)
    assert m['checked'] == 1 and [u['checked'] for u in m['units']] == [False, True]      # reste à faire en premier
    c.post(f'/api/missions/{mid}/check', headers=h['mag'], json={'unit_id': units[1]})
    assert c.post(f'/api/missions/{mid}/status', headers=h['mag'], json={'action': 'complete', 'note': 'Palettes filmées et prêtes quai 2'}).status_code == 200
    pdf = c.get(f'/api/reports/mission/{mid}', headers=h['expl'])
    assert pdf.status_code == 200
    t = pdf_text(pdf.content)
    assert 'RÉCAPITULATIF DE MISSION' in t.upper() and 'TERMINÉE' in t and 'Filmer la palette' in t and rec in t
    assert all(u in t for u in units) and 'AFR-TEMP' in t and 'Prise en charge' in t


def test_free_task_and_unit_subset(env):
    c, h = env['c'], env['h']
    rec, units = stocked_receipt(env)
    assert c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'type': 'autre'}).status_code == 400   # texte libre obligatoire
    r = c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'type': 'autre', 'description': 'Prendre 4 photos des étiquettes', 'unit_ids': [units[1]], 'assignee': 'mag'})
    assert r.status_code == 200 and r.json()['status'] == 'assigned'
    assert c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'unit_ids': ['UNIT-AUTRE']}).status_code == 400
    m = next(x for x in c.get('/api/missions', headers=h['expl']).json() if x['id'] == r.json()['id'])
    assert m['type'] == 'autre' and m['receipt_id'] == rec and units[1] in m['unit_ids'] and units[0] not in m['unit_ids']
    assert c.get('/api/missions/feed', headers=h['mag']).json()['count'] == 1             # affectée à moi


def test_receipt_full_history(env):
    c, h, server = env['c'], env['h'], env['server']
    rec, units = stocked_receipt(env)
    mid = c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'description': 'Préparer'}).json()['id']
    c.post(f'/api/missions/{mid}/status', headers=h['mag'], json={'action': 'take'})
    c.post(f'/api/receipts/{rec}/discrepancy', headers=h['mag'], json={'kind': 'damage', 'description': 'Coin enfoncé'})
    r = c.get(f'/api/receipts/{rec}/history', headers=h['expl'])
    assert r.status_code == 200
    titles = [e['title'] for e in r.json()['events']]
    assert titles[0] == 'Réception enregistrée'
    for t in ('Demande au magasin', 'Mission prise en charge', 'Écart déclaré'):
        assert t in titles, (t, titles)
    assert any('Blocage' in t for t in titles)
    assert c.get(f'/api/receipts/{rec}/history', headers=h['expl_mar']).status_code == 403
    t = pdf_text(c.get(f'/api/receipts/{rec}/report', headers=h['expl']).content)
    assert 'Historique complet' in t and 'Mission prise en charge' in t


def test_dashboard_flow_live_and_recent(env):
    c, h = env['c'], env['h']
    rec, units = stocked_receipt(env)
    bad = env['receipt'](expected=4, actual=3)
    mid = c.post(f'/api/receipts/{rec}/missions', headers=h['expl'], json={'description': 'Préparer'}).json()['id']
    d = c.get('/api/dashboard/ops', headers=h['expl'], params={'warehouse': 'Afrique'}).json()
    assert d['flow']['received'] == 2 and d['flow']['in_stock'] == 2 and d['flow']['preparing'] == 1
    assert [w['id'] for w in d['waiting']] == [mid] and d['live'] == []
    c.post(f'/api/missions/{mid}/status', headers=h['mag'], json={'action': 'take'})
    d = c.get('/api/dashboard/ops', headers=h['expl'], params={'warehouse': 'Afrique'}).json()
    assert d['live'][0]['assignee'] == 'mag' and d['waiting'] == []
    recent = {r['id']: r for r in d['recent']}
    assert recent[bad]['problem'] is True and recent[rec]['problem'] is False and recent[rec]['missions'] == 1


# --- Lot 18 : statut des racks, stockage interne TAF, suppression en bloc ---------------------------
def _racks(env):
    gen(env, kind='rack', names=['G', 'D'], levels=2, positions=3, capacity_kg=1000, capacity_m3=3, proof='Plaque constructeur')


def test_location_status_rules(env):
    c, h = env['c'], env['h']
    _racks(env)
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['mag'], json={'status': 'endommage', 'note': ''}).status_code == 400   # motif obligatoire
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['mag'], json={'status': 'endommage', 'note': 'Lisse tordue'}).status_code == 200
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['mag'], json={'status': 'ok'}).status_code == 403                     # remise en service : responsable
    rec = env['receipt']()
    unit = env['unit'](rec, placed=False).json()['id']
    v = c.get('/api/units', headers=h['mag']).json()[0]['version']
    r = c.post('/api/move', headers=h['mag'], json={'unit_id': unit, 'destination': 'AFR-G-1-01', 'expected_version': v})
    assert r.status_code == 409 and 'endommagé' in r.text
    plan = c.get('/api/locations/plan', headers=h['mag'], params={'warehouse': 'Afrique'}).json()
    cell = {x['id']: x for rk in plan['racks'] for lv in rk['levels'] for x in lv['cells']}['AFR-G-1-01']
    assert cell['state'] == 'endommage' and cell['status_label'] == 'Endommagé' and cell['status_note'] == 'Lisse tordue'
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['resp'], json={'status': 'ok', 'note': 'Lisse remplacée'}).status_code == 200
    # Rack entier
    r = c.post('/api/locations/structure-status', headers=h['mag'], json={'warehouse': 'Afrique', 'structure': 'D', 'status': 'inspection', 'note': 'Contrôle annuel'})
    assert r.status_code == 200 and r.json()['updated'] == 6
    hist = c.get('/api/locations/AFR-D-2-03/detail', headers=h['mag']).json()['history']
    assert hist[0]['action'] == 'location_status' and hist[0]['details']['to'] == 'inspection'


def test_internal_storage_and_detail(env):
    c, h = env['c'], env['h']
    _racks(env)
    r = c.post('/api/locations/AFR-G-2-02/internal', headers=h['mag'], json={'description': 'Films étirables et feuillards', 'service': 'Magasin', 'quantity': '12 rouleaux'})
    assert r.status_code == 200
    d = c.get('/api/locations/AFR-G-2-02/detail', headers=h['mag']).json()
    assert d['internal']['description'] == 'Films étirables et feuillards' and d['internal']['since']
    plan = c.get('/api/locations/plan', headers=h['mag'], params={'warehouse': 'Afrique'}).json()
    assert plan['summary']['internal'] == 1
    rec = env['receipt']()
    unit = env['unit'](rec, placed=False).json()['id']
    v = next(x for x in c.get('/api/units', headers=h['mag']).json() if x['id'] == unit)['version']
    r = c.post('/api/move', headers=h['mag'], json={'unit_id': unit, 'destination': 'AFR-G-2-02', 'expected_version': v})
    assert r.status_code == 409 and 'stockage interne' in r.text
    assert any(x['id'] == unit for x in c.get('/api/locations/AFR-G-1-03/detail', headers=h['mag']).json()['candidates'])
    assert c.post('/api/move', headers=h['mag'], json={'unit_id': unit, 'destination': 'AFR-G-1-03', 'expected_version': v}).status_code == 200
    d = c.get('/api/locations/AFR-G-1-03/detail', headers=h['mag']).json()
    assert d['units'][0]['receipt_id'] == rec                                    # le clic ouvre le dossier de cette entrée
    assert c.post('/api/locations/AFR-G-1-03/internal', headers=h['mag'], json={'description': 'Archives'}).status_code == 409
    assert c.post('/api/locations/AFR-G-2-02/internal/release', headers=h['mag'], json={'note': 'Consommés'}).status_code == 200
    assert c.get('/api/locations/AFR-G-2-02/detail', headers=h['mag']).json()['internal'] is None
    assert c.post('/api/locations/AFR-G-2-02/internal', headers=h['mag_mar'], json={'description': 'xxx'}).status_code == 403


def test_remove_all_racks_of_warehouse(env):
    c, h = env['c'], env['h']
    _racks(env)
    gen(env, kind='floor', names=['A'], positions=2)
    rec = env['receipt']()
    unit = env['unit'](rec, placed=False).json()['id']
    v = next(x for x in c.get('/api/units', headers=h['mag']).json() if x['id'] == unit)['version']
    c.post('/api/move', headers=h['mag'], json={'unit_id': unit, 'destination': 'AFR-D-1-01', 'expected_version': v})
    c.post('/api/locations/AFR-G-1-02/internal', headers=h['mag'], json={'description': 'Palettes vides'})
    body = {'warehouse': 'Afrique', 'scope': 'rack', 'reason': 'Réaménagement'}
    assert c.post('/api/locations/remove-all', headers=h['mag'], json=body).status_code == 403
    r = c.post('/api/locations/remove-all', headers=h['resp'], json=body)
    assert r.status_code == 200, r.text
    assert sorted(r.json()['kept']) == ['AFR-D-1-01', 'AFR-G-1-02']                  # occupés : conservés
    ids = {l['id'] for l in c.get('/api/locations', headers=h['mag'], params={'warehouse': 'Afrique'}).json()}
    assert 'AFR-G-2-03' not in ids and 'AFR-R01-A1' not in ids and {'AFR-D-1-01', 'AFR-G-1-02', 'AFR-SOL-A-01', 'AFR-TEMP'} <= ids
    r = c.post('/api/locations/remove-all', headers=h['resp'], json={**body, 'scope': 'all'})
    ids = {l['id'] for l in c.get('/api/locations', headers=h['mag'], params={'warehouse': 'Afrique'}).json()}
    assert 'AFR-SOL-A-01' not in ids and 'AFR-TEMP' in ids


def test_closed_location_status(env):
    c, h = env['c'], env['h']
    _racks(env)
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['mag'], json={'status': 'ferme', 'note': 'Zone condamnée'}).status_code == 403
    assert c.put('/api/locations/AFR-G-1-01/status', headers=h['resp'], json={'status': 'ferme', 'note': 'Zone condamnée'}).status_code == 200
    plan = c.get('/api/locations/plan', headers=h['mag'], params={'warehouse': 'Afrique'}).json()
    cell = {x['id']: x for rk in plan['racks'] for lv in rk['levels'] for x in lv['cells']}['AFR-G-1-01']
    assert cell['state'] == 'blocked' and cell['status_label'] == 'Emplacement fermé'


def test_reserve_without_note(env):
    c, h = env['c'], env['h']
    _racks(env)
    assert c.put('/api/locations/AFR-G-1-03/status', headers=h['resp'], json={'status': 'reserve'}).status_code == 200
    assert c.put('/api/locations/AFR-G-1-03/status', headers=h['resp'], json={'status': 'ok'}).status_code == 200
