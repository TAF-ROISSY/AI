"""Lot 17 : fiche d'entrée en attente de complément, modification tracée, historique inaltérable, validation finale, récapitulatif."""
import io
import pytest
from pypdf import PdfReader


def pdf_text(raw):
    return ' '.join(' '.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages).split())


def entry(env, dims=False, awb=''):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]
    d = {'length_cm': 120, 'width_cm': 80, 'height_cm': 150} if dims else {}
    drv = c.post('/api/drivers', headers=h['mag'], json={'name': 'Ali Diallo', 'company': 'Trans Sahel', 'id_type': 'passeport', 'id_number': 'P998877'}).json()['id']
    r = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl['id'], 'awb': awb, 'expected': 2, 'actual': 2, 'weight': 300, 'shipper': 'SODECO', 'transport_ref': 'CMR-1', 'driver_id': drv, 'pallets_expected': 2,
                                                         'packages': [{'kind': 'palette', 'weight_kg': 150, 'packages': 1, **d}] * 2})
    assert r.status_code == 200, r.text
    return r.json()['id'], r.json()['units']


def dossier(env, rid, who='mag'):
    return env['c'].get(f'/api/receipts/{rid}/dossier', headers=env['h'][who]).json()


def transport_doc(env, rid, who='mag'):
    return env['c'].post(f'/api/documents/receipt/{rid}', headers=env['h'][who], params={'category': 'transport'}, files={'file': ('lta.pdf', b'%PDF-1.4 lta', 'application/pdf')})


def test_entry_without_dims_is_pending_and_cannot_be_validated(env):
    c, h = env['c'], env['h']
    rid, units = entry(env)
    d = dossier(env, rid)
    assert d['state']['stage'] == 'pending'
    miss = ' '.join(d['state']['missing'])
    assert 'Dimensions manquantes : 2' in miss and 'document de transport' in miss
    assert all(u['volume'] is None for u in d['units'])
    # Étiquettes de traçabilité disponibles dès l'entrée
    assert c.get('/api/labels-batch', headers=h['mag'], params={'ids': ','.join(units)}).status_code == 200
    r = c.post(f'/api/receipts/{rid}/validate', headers=h['mag'])
    assert r.status_code == 409 and 'Fiche incomplète' in r.text
    assert c.get('/api/receipts', headers=h['mag']).json()[0]['missing']
    t = pdf_text(c.get(f'/api/receipts/{rid}/report', headers=h['mag']).content)
    assert 'EN ATTENTE DE COMPLÉMENT' in t


def test_complete_edit_and_validate(env):
    c, h, server = env['c'], env['h'], env['server']
    server.MAIL_BACKEND = 'memory'; server.MAIL_DELAY = 0; server.MAIL_SENT.clear()
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['christophe@taftrans.fr']})
    rid, units = entry(env)
    assert server.process_mail_outbox() == 0                                           # rien n'est envoyé avant la validation
    assert c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'awb': '057-12345678', 'carrier': 'Trans Sahel'}).status_code == 200
    assert c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'awb': '057-12345678'}).status_code == 400   # aucune modification
    for u in units:
        r = c.put(f'/api/units/{u}/dimensions', headers=h['mag'], json={'length_cm': 120, 'width_cm': 80, 'height_cm': 140})
        assert r.status_code == 200 and r.json()['volume_m3'] == 1.344
    assert transport_doc(env, rid).status_code == 200
    d = dossier(env, rid)
    assert d['state']['missing'] == [] and d['receipt']['volume_m3'] == 2.688
    r = c.post(f'/api/receipts/{rid}/validate', headers=h['mag'])
    assert r.status_code == 200 and r.json()['revision'] == 1 and r.json()['mail']
    assert server.process_mail_outbox() == 1 and rid in server.MAIL_SENT[-1]['subject']
    assert 'BORDEREAU DE RECEPTION' in pdf_text(server.MAIL_SENT[-1]['attachments'][0][1])
    # Fiche validée : verrouillée
    assert c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'notes': 'x'}).status_code == 409
    assert c.put(f'/api/units/{units[0]}/dimensions', headers=h['mag'], json={'length_cm': 1, 'width_cm': 1, 'height_cm': 1}).status_code == 409
    titles = [e['title'] for e in dossier(env, rid)['history']]
    for t in ('Réception enregistrée', 'Fiche modifiée', 'Dimensions saisies', 'Document ajouté', 'Validation définitive de la fiche', 'Fiche de réception envoyée par e-mail'):
        assert t in titles, (t, titles)
    edit = next(e for e in dossier(env, rid)['history'] if e['title'] == 'Fiche modifiée')
    assert 'LTA : « — » → « 057-12345678 »' in edit['detail'] and edit['actor'] == 'mag'
    cover = c.get(f'/api/receipts/{rid}/cover', headers=h['mag'])
    t = pdf_text(cover.content)
    assert cover.status_code == 200 and rid in t and 'Documents à agrafer' in t and 'VALIDÉE' in t


def test_reopen_and_revalidate(env):
    c, h, server = env['c'], env['h'], env['server']
    server.MAIL_BACKEND = 'memory'; server.MAIL_DELAY = 0; server.MAIL_SENT.clear()
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['christophe@taftrans.fr']})
    rid, units = entry(env, dims=True, awb='057-1')
    transport_doc(env, rid)
    c.post(f'/api/receipts/{rid}/validate', headers=h['mag']); server.process_mail_outbox()
    assert c.post(f'/api/receipts/{rid}/reopen', headers=h['mag'], json={'reason': 'Erreur de poids'}).status_code == 403
    assert c.post(f'/api/receipts/{rid}/reopen', headers=h['expl'], json={'reason': 'Erreur de poids'}).status_code == 200
    assert c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'weight': 310}).status_code == 200
    assert c.post(f'/api/receipts/{rid}/validate', headers=h['mag']).json()['revision'] == 2
    server.process_mail_outbox()
    assert '(fiche modifiée)' in server.MAIL_SENT[-1]['subject']
    titles = [e['title'] for e in dossier(env, rid)['history']]
    assert titles.count('Validation définitive de la fiche') == 2 and 'Fiche rouverte pour modification' in titles


def test_security_edit_adds_hold(env):
    c, h = env['c'], env['h']
    rid, units = entry(env, dims=True)
    c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'security_status': 'a_controler'})
    holds = c.get(f'/api/units/{units[0]}/holds', headers=h['expl']).json()
    assert any('Sûreté' in x['reason'] for x in holds)


def test_history_cannot_be_altered(env):
    server = env['server']
    entry(env)
    with server.db() as db:
        with pytest.raises(Exception, match='inaltérable'):
            db.execute("UPDATE audit SET actor='pirate'")
    with server.db() as db:
        with pytest.raises(Exception, match='inaltérable'):
            db.execute('DELETE FROM audit')
    with server.db() as db:
        assert db.execute("SELECT COUNT(*) FROM audit WHERE actor='pirate'").fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0] > 0


def test_other_warehouse_cannot_edit(env):
    rid, units = entry(env)
    c, h = env['c'], env['h']
    assert c.put(f'/api/receipts/{rid}', headers=h['mag_mar'], json={'notes': 'x'}).status_code == 403
    assert c.get(f'/api/receipts/{rid}/dossier', headers=h['mag_mar']).status_code == 403
    assert c.post(f'/api/documents/receipt/{rid}', headers=h['mag'], params={'category': 'pirate'}, files={'file': ('a.pdf', b'%PDF-1', 'application/pdf')}).status_code == 400


def test_mail_contains_links_to_documents(env):
    c, h, server = env['c'], env['h'], env['server']
    server.MAIL_BACKEND = 'memory'; server.MAIL_DELAY = 0; server.MAIL_SENT.clear(); server.PUBLIC_URL = 'https://warehouse.example'
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['christophe@taftrans.fr']})
    rid, _ = entry(env, dims=True, awb='057-9')
    did = transport_doc(env, rid).json()['id']
    c.post(f'/api/receipts/{rid}/validate', headers=h['mag']); server.process_mail_outbox()
    text = server.MAIL_SENT[-1]['text']
    assert f'https://warehouse.example/#entree={rid}' in text and f'#entree={rid}&doc={did}' in text and 'lta.pdf (document de transport)' in text
    assert 'connexion TAF WAREHOUSE requise' in text


def test_validated_sheet_is_the_dgac_form(env):
    c, h, server = env['c'], env['h'], env['server']
    server.MAIL_BACKEND = 'memory'; server.MAIL_DELAY = 0; server.MAIL_SENT.clear()
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['christophe@taftrans.fr']})
    rid, units = entry(env, dims=True, awb='057-12345678')
    c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'nature': 'Pièces détachées', 'consignee': 'TAF CLIENT', 'apparent_condition': 'endommage'})
    transport_doc(env, rid)
    before = pdf_text(c.get(f'/api/receipts/{rid}/report', headers=h['mag']).content)
    assert 'Fiche de réception' in before and 'BORDEREAU' not in before         # fiche de travail tant que non validée
    assert c.post(f'/api/receipts/{rid}/validate', headers=h['mag']).status_code == 200
    r = c.get(f'/api/receipts/{rid}/report', headers=h['mag'])
    assert 'bordereau-reception' in r.headers['content-disposition']
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2
    t = pdf_text(r.content)
    for expected in ('BORDEREAU DE RECEPTION', 'Regulated Agent', 'Version 2.5', 'SODECO', 'TAF CLIENT', 'Ali Diallo', 'Trans Sahel', 'P998877',
                     'Pièces détachées', 'LTA 057-12345678', 'Emballage endommagé', 'Mag', '120', '80', '150 kg', '240 kg'):
        assert expected in t, expected
    # Le modèle officiel est conservé tel quel : mêmes éléments que le PDF d'origine.
    template = PdfReader(str(server.Path(server.__file__).parent / 'templates' / 'bordereau_reception_v2_5.pdf'))
    assert reader.pages[0].mediabox == template.pages[0].mediabox
    server.process_mail_outbox()
    assert server.MAIL_SENT[-1]['attachments'][0][0] == f'bordereau-reception-{rid}.pdf'


def test_validation_requires_driver_and_reasons(env):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]
    body = {'warehouse': 'Afrique', 'client_id': cl['id'], 'awb': '1', 'expected': 1, 'actual': 1, 'weight': 10,
            'packages': [{'kind': 'fut', 'length_cm': 60, 'width_cm': 60, 'height_cm': 90, 'weight_kg': 10, 'packages': 1}]}
    r = c.post('/api/receipts', headers=h['mag'], json=body, _no_driver=True)
    assert r.status_code == 400 and 'chauffeur' in r.text                      # chauffeur obligatoire avant de valider l'entrée
    rid = c.post('/api/receipts', headers=h['mag'], json=body).json()['id']
    transport_doc(env, rid)
    miss = ' '.join(dossier(env, rid)['state']['missing'])
    assert 'Expéditeur' in miss
    c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'accepted': False, 'shipper': 'X'})
    assert 'raisons' in ' '.join(dossier(env, rid)['state']['missing'])
    assert dossier(env, rid)['units'][0]['unit_type'] == 'fut'


def test_cancel_wrong_entry(env):
    c, h, server = env['c'], env['h'], env['server']
    rid, units = entry(env, dims=True, awb='057-9')
    putaway_unit = units[0]
    from helpers import putaway
    putaway(server, putaway_unit)
    mid = c.post(f'/api/receipts/{rid}/missions', headers=h['expl'], json={'description': 'Préparer'}).json()['id']
    assert c.post(f'/api/receipts/{rid}/cancel', headers=h['mag_mar'], json={'reason': 'Erreur de saisie'}).status_code == 403
    assert c.post(f'/api/receipts/{rid}/cancel', headers=h['mag'], json={'reason': 'x'}).status_code == 422   # motif obligatoire
    r = c.post(f'/api/receipts/{rid}/cancel', headers=h['mag'], json={'reason': 'Doublon de la fiche E-000002'})
    assert r.status_code == 200 and r.json()['units'] == 2
    d = dossier(env, rid)
    assert d['state']['stage'] == 'cancelled' and d['receipt']['cancel_reason'] == 'Doublon de la fiche E-000002'
    assert 'Fiche annulée (erreur)' in [e['title'] for e in d['history']]
    assert all(u['id'] not in units for u in c.get('/api/units', headers=h['mag']).json())     # retirées du stock
    assert next(m for m in c.get('/api/missions', headers=h['expl']).json() if m['id'] == mid)['status'] == 'cancelled'
    assert c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'notes': 'x'}).status_code == 409
    assert c.post(f'/api/receipts/{rid}/cancel', headers=h['mag'], json={'reason': 'Encore une fois'}).status_code == 409
    nxt, _ = entry(env)
    assert nxt != rid and int(nxt[2:]) == int(rid[2:]) + 1                     # numéro jamais réutilisé
    with server.db() as db:                                                      # rien n'est effacé
        assert db.execute('SELECT COUNT(*) FROM units WHERE receipt_id=?', (rid,)).fetchone()[0] == 2


def test_cancel_refused_after_exit_or_validation(env):
    c, h = env['c'], env['h']
    rid, units = entry(env, dims=True, awb='057-9')
    transport_doc(env, rid)
    c.post(f'/api/receipts/{rid}/validate', headers=h['mag'])
    r = c.post(f'/api/receipts/{rid}/cancel', headers=h['expl'], json={'reason': 'Erreur de client'})
    assert r.status_code == 409 and 'rouvrir' in r.text
    rid2, units2 = entry(env)
    assert c.post(f'/api/receipts/{rid2}/cancel', headers=h['expl2'], json={'reason': 'Erreur de client'}).status_code == 200   # exploitation
    rid3, _ = entry(env)
    other = c.post('/api/users', headers=h['admin'], json={'username': 'mag2', 'pin': '482915', 'role': 'worker', 'warehouses': ['Afrique']})
    tok = c.post('/api/login', json={'username': 'mag2', 'password': '482915'}).json()['token']
    assert c.post(f'/api/receipts/{rid3}/cancel', headers={'Authorization': 'Bearer ' + tok}, json={'reason': 'Pas ma fiche'}).status_code == 403


def test_missing_packing_lines_created_automatically(env):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]
    rid = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl['id'], 'expected': 5, 'actual': 5, 'weight': 345}).json()['id']
    assert dossier(env, rid)['units'] == []
    r = c.post(f'/api/receipts/{rid}/lines', headers=h['mag'], json={})
    assert r.status_code == 200 and r.json()['created'] == 5
    units = dossier(env, rid)['units']
    assert [(u['unit_type'], u['unit_index'], u['unit_count'], u['quantity']) for u in units] == [('colis', i, 5, 1) for i in range(1, 6)]
    assert c.post(f'/api/receipts/{rid}/lines', headers=h['mag'], json={}).status_code == 409   # rien de plus à créer
    r = c.put(f"/api/units/{units[0]['id']}/dimensions", headers=h['mag'], json={'length_cm': 120, 'width_cm': 80, 'height_cm': 100, 'weight_kg': 70, 'unit_type': 'palette'})
    assert r.status_code == 200 and dossier(env, rid)['units'][0]['unit_type'] == 'palette'
    assert c.put(f"/api/units/{units[1]['id']}/dimensions", headers=h['mag'], json={'unit_type': 'fut', 'weight_kg': 40}).status_code == 200   # type seul
    assert c.put(f"/api/units/{units[1]['id']}/dimensions", headers=h['mag'], json={'length_cm': 50}).status_code == 400
    assert 'Lignes de colisage créées' in [e['title'] for e in dossier(env, rid)['history']]
    rec = next(x for x in c.get('/api/receipts', headers=h['mag']).json() if x['id'] == rid)
    assert rec['status'] == 'received'                                          # pas d'écart de poids fictif


def test_driver_mandatory_fields_and_simple_unit_numbers(env):
    c, h = env['c'], env['h']
    for body in ({'name': 'Ali'}, {'name': 'Ali Diallo', 'company': 'Trans'}, {'name': 'Ali Diallo', 'company': '', 'id_type': 'CNI', 'id_number': 'X'}):
        assert c.post('/api/drivers', headers=h['mag'], json=body, _raw=True).status_code == 400
    assert c.post('/api/drivers', headers=h['mag'], json={'name': 'Ali DIALLO', 'company': 'Trans Sahel', 'id_type': 'CNI', 'id_number': 'X1'}, _raw=True).status_code == 200
    rid, units = entry(env)
    assert units == [f'{rid}-01', f'{rid}-02']                                   # numérotation simple : entrée + rang


def test_validation_requires_weight_count_shipper_and_transport_number(env):
    c, h = env['c'], env['h']
    rid, units = entry(env, dims=True)
    transport_doc(env, rid)
    c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'transport_ref': '', 'weight': 0})
    miss = ' '.join(dossier(env, rid)['state']['missing'])
    assert 'document de transport manquant' in miss.lower() and 'Poids brut' in miss
    c.put(f'/api/receipts/{rid}', headers=h['mag'], json={'transport_ref': 'CMR-77', 'weight': 300})
    assert dossier(env, rid)['state']['missing'] == []                           # LTA, destinataire, réf. dossier facultatifs


def test_document_download_keeps_type_and_name(env):
    """Lot 22 : « Ouvrir » affiche les photos et PDF (type et nom réels), jamais de HTML exécutable."""
    c, h = env['c'], env['h']
    rid, _ = entry(env)
    for name, raw, mime, expect in [('remas.jpg', b'\xff\xd8\xff\xe0jpg', 'image/jpeg', 'image/jpeg'), ('lta.pdf', b'%PDF-1.4 x', 'application/pdf', 'application/pdf'),
                                    ('piege.html', b'<script>alert(1)</script>', 'text/html', 'application/octet-stream')]:
        up = c.post(f'/api/documents/receipt/{rid}', headers=h['mag'], params={'category': 'photo'}, files={'file': (name, raw, mime)})
        if up.status_code != 200:
            assert name.endswith('.html'), up.text
            continue
        r = c.get(f"/api/documents/{up.json()['id']}/download", headers=h['mag'])
        assert r.status_code == 200 and r.content == raw
        assert r.headers['content-type'].split(';')[0] == expect
        assert name in r.headers['content-disposition'] and r.headers['x-content-type-options'] == 'nosniff'
