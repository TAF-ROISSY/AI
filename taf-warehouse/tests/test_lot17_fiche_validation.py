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
    r = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl['id'], 'awb': awb, 'expected': 2, 'actual': 2, 'weight': 300,
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
    assert 'Dimensions manquantes : 2' in miss and 'Document de transport' in miss and 'LTA' in miss
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
    assert 'RÉCEPTION CONFORME' in pdf_text(server.MAIL_SENT[-1]['attachments'][0][1])
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
