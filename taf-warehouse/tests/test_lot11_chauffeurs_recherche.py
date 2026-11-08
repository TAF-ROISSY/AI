"""Pièce d'identité des chauffeurs et recherche des mouvements avec filtres."""
import csv, io
from helpers import signature, putaway, png_bytes


def driver(env, name='Jean Martin', company='Transports Dupont', plate='AB-123-CD', **extra):
    r = env['c'].post('/api/drivers', headers=env['h']['mag'], json={'name': name, 'company': company, 'plate': plate, **extra})
    assert r.status_code == 200, r.text
    return r.json()['id']


# --- Pièce d'identité ---

def test_driver_identity_photo_is_private(env):
    c, h = env['c'], env['h']
    d = driver(env, id_type='CNI', id_number='X1234567')
    up = c.post(f'/api/documents/driver/{d}', headers=h['mag'], files={'file': ('cni.png', png_bytes(), 'image/png')})
    assert up.status_code == 200, up.text
    row = next(x for x in c.get('/api/drivers', headers=h['mag']).json() if x['id'] == d)
    assert row['id_type'] == 'CNI' and row['has_identity'] == 1
    assert 'id_number' not in row  # numéro masqué pour le magasin
    full = next(x for x in c.get('/api/drivers', headers=h['expl']).json() if x['id'] == d)
    assert full['id_number'] == 'X1234567'
    docs = c.get('/api/documents', params={'kind': 'driver', 'ref': d}, headers=h['expl']).json()
    assert len(docs) == 1
    assert c.get(f"/api/documents/{docs[0]['id']}/download", headers=h['expl']).content == png_bytes()
    # Le magasin dépose la photo mais ne la consulte pas.
    assert c.get('/api/documents', params={'kind': 'driver', 'ref': d}, headers=h['mag']).status_code == 403
    assert c.get(f"/api/documents/{docs[0]['id']}/download", headers=h['mag']).status_code == 403
    assert c.post('/api/documents/driver/DRV-INCONNU', headers=h['mag'], files={'file': ('cni.png', png_bytes(), 'image/png')}).status_code == 404


# --- Recherche des mouvements ---

def scenario(env):
    """Deux sorties signées par deux chauffeurs différents, plus des réceptions."""
    c, h = env['c'], env['h']
    d1, d2 = driver(env, 'Jean Martin', plate='AB-123-CD'), driver(env, 'Ali Diallo', 'Trans Sahel', 'EF-456-GH')
    rec = env['receipt'](expected=8, actual=8)
    u1 = env['unit'](rec, quantity=4, weight=400).json()['id']
    u2 = env['unit'](rec, quantity=4, weight=400).json()['id']
    for u, d in ((u1, d1), (u2, d2)):
        oid = c.post('/api/release-orders', headers=h['expl'], json={'warehouse': 'Afrique', 'reference': 'DOS-' + u[-4:], 'lines': [{'unit_id': u, 'quantity': 2}]}).json()['id']
        c.post(f'/api/release-orders/{oid}/prepare', headers=h['mag'], json={'unit_id': u, 'note': 'Contrôlé'})
        c.post(f'/api/release-orders/{oid}/authorize', headers=h['expl'])
        r = c.post(f'/api/release-orders/{oid}/complete', headers=h['mag'], json={'driver_id': d, 'signature_name': 'Signataire', 'signature_data': signature(), 'signature_consent': True})
        assert r.status_code == 200, r.text
    return d1, d2, u1, u2, rec


def search(env, **params):
    r = env['c'].get('/api/movements/search', headers=env['h']['expl'], params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_search_by_driver_kind_and_dates(env):
    d1, d2, u1, u2, rec = scenario(env)
    res = search(env, driver_id=d1)
    assert res['total'] == 1 and res['items'][0]['unit_id'] == u1
    item = res['items'][0]
    assert item['driver_name'] == 'Jean Martin' and item['driver_plate'] == 'AB-123-CD' and item['kind'] == 'exit'
    assert item['client'] == 'CLIENT DEMO' and 'awb' in item and item['receipt_id'] == rec
    assert search(env, kind='exit')['total'] == 2
    assert search(env, kind='receive')['total'] == 2
    assert search(env, date_from='2000-01-01', date_to='2000-12-31')['total'] == 0
    today = item['at'][:10]
    assert search(env, date_from=today, date_to=today)['total'] == 4


def test_search_free_text_actor_client_and_pagination(env):
    d1, d2, u1, u2, rec = scenario(env)
    assert search(env, q='EF-456')['total'] == 1          # immatriculation
    assert search(env, q='diallo')['total'] == 1          # nom du chauffeur, sans casse
    assert search(env, q=u2[-6:])['total'] == 2           # unité : réception + sortie
    assert search(env, actor='mag', kind='exit')['total'] == 2
    cl = env['c'].get('/api/clients', headers=env['h']['admin']).json()[0]['id']
    assert search(env, client_id=cl)['total'] == 4
    page = search(env, limit=3, offset=0)
    assert len(page['items']) == 3 and page['total'] == 4
    assert len(search(env, limit=3, offset=3)['items']) == 1


def test_search_respects_warehouse_rights_and_exports_csv(env):
    scenario(env)
    c, h = env['c'], env['h']
    assert c.get('/api/movements/search', headers=h['expl_mar']).json()['total'] == 0
    assert c.get('/api/movements/search', params={'warehouse': 'Afrique'}, headers=h['expl_mar']).status_code == 403
    r = c.get('/api/movements/search', params={'kind': 'exit', 'format': 'csv'}, headers=h['expl'])
    assert r.status_code == 200 and 'text/csv' in r.headers['content-type']
    rows = list(csv.reader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))
    assert rows[0][:3] == ['Date', 'Type', 'Unité'] and len(rows) == 3
    assert any('Jean Martin' in ' '.join(x) for x in rows[1:])
