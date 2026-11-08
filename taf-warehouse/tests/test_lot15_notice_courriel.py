"""Lot 14 : notice transporteur, effacement des pièces d'identité à 1 an, fiche de réception envoyée par e-mail."""
import io
from datetime import datetime, timedelta, timezone
from pypdf import PdfReader
from helpers import png_bytes


def pdf_text(raw):
    return ' '.join(' '.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages).split())


def old(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='seconds')


def driver(env, **extra):
    c, h = env['c'], env['h']
    d = c.post('/api/drivers', headers=h['mag'], json={'name': 'Moussa Traoré', 'company': 'Trans Sahel', 'plate': 'AB-123-CD', 'id_type': 'passeport', 'id_number': 'P12345678', **extra}).json()['id']
    assert c.post(f'/api/documents/driver/{d}', headers=h['mag'], files={'file': ('piece.png', png_bytes(), 'image/png')}).status_code == 200
    return d


def test_notice_blank_and_personalised(env):
    c, h = env['c'], env['h']
    r = c.get('/api/drivers/notice', headers=h['mag'])
    assert r.status_code == 200 and r.headers['content-type'] == 'application/pdf'
    t = pdf_text(r.content)
    assert len(PdfReader(io.BytesIO(r.content)).pages) == 2                       # français puis anglais
    assert '2015/1998' in t and 'un an après votre dernier passage' in t and 'one year after your last visit' in t
    assert 'christophe@taftrans.fr' in t and 'CNIL' in t
    d = driver(env)
    t = pdf_text(c.get(f'/api/drivers/{d}/notice', headers=h['expl']).content)
    assert 'Moussa Traoré' in t and '5678' in t and 'P1234' not in t                # numéro masqué
    erase = (datetime.now(timezone.utc) + timedelta(days=365)).strftime('%d/%m/%Y')
    assert erase in t
    t = pdf_text(c.get(f'/api/drivers/{d}/notice', headers=h['mag']).content)
    assert '5678' not in t                                                         # magasin : pas de numéro


def test_identity_erased_one_year_after_last_visit(env):
    c, h, server = env['c'], env['h'], env['server']
    recent, stale = driver(env), driver(env, name='Ancien chauffeur')
    with server.db() as db:
        for t, col in (('drivers', 'created'),):
            db.execute(f'UPDATE {t} SET {col}=? WHERE id=?', (old(400), stale))
        db.execute("UPDATE documents SET uploaded=? WHERE kind='driver' AND ref=?", (old(400), stale))
        db.execute("UPDATE documents SET uploaded=? WHERE kind='driver' AND ref=?", (old(300), recent))
        db.execute('UPDATE drivers SET created=? WHERE id=?', (old(500), recent))
        paths = [r['path'] for r in db.execute("SELECT path FROM documents WHERE kind='driver' AND ref=?", (stale,)).fetchall()]
    rows = {r['id']: r for r in c.get('/api/drivers', headers=h['expl']).json()}
    assert rows[stale]['erase_on'] < datetime.now(timezone.utc).isoformat() < rows[recent]['erase_on']
    assert c.post('/api/admin/purge-identities', headers=h['expl']).status_code == 403
    r = c.post('/api/admin/purge-identities', headers=h['admin'])
    assert r.status_code == 200 and r.json()['purged'] == [stale]
    rows = {r['id']: r for r in c.get('/api/drivers', headers=h['expl']).json()}
    assert rows[stale]['has_identity'] == 0 and rows[stale]['id_number'] == '' and rows[stale]['identity_erased_at']
    assert rows[stale]['name'] == 'Ancien chauffeur'                               # le nom reste (bons de remise)
    assert rows[recent]['has_identity'] == 1 and rows[recent]['id_number'] == 'P12345678'
    from pathlib import Path
    assert all(not Path(p).exists() for p in paths)
    assert c.post('/api/admin/purge-identities', headers=h['admin']).json()['purged'] == []   # idempotent
    audit = c.get('/api/audit', headers=h['admin']).json()
    assert any(a['action'] == 'purge_identity' and a['ref'] == stale for a in audit)


def test_recent_handover_extends_retention(env):
    c, h, server = env['c'], env['h'], env['server']
    d = driver(env)
    with server.db() as db:
        db.execute('UPDATE drivers SET created=? WHERE id=?', (old(800), d))
        db.execute("UPDATE documents SET uploaded=? WHERE kind='driver' AND ref=?", (old(800), d))
        db.execute("INSERT INTO transfers(id,unit_id,source,destination,status,created,actor,driver_id,dispatched_at) VALUES('TRF-X','UNIT-X','Afrique','Maritime','received',?,'mag',?,?)", (old(10), d, old(10)))
    assert server.purge_identities() == []


def mail_env(env, to=('christophe@taftrans.fr',)):
    server = env['server']
    server.MAIL_BACKEND = 'memory'; server.MAIL_DELAY = 0; server.MAIL_SENT.clear()
    for wh in ('Afrique', 'Moyen-Orient'):
        assert env['c'].put(f'/api/mail-routes/{wh}', headers=env['h']['admin'], json={'recipients': list(to)}).status_code == 200
    return server


def receipt(env, **over):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]
    pk = [{'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 150, 'weight_kg': 200, 'packages': 2}] * 2
    body = {'warehouse': 'Afrique', 'client_id': cl['id'], 'awb': '057-11112222', 'expected': 4, 'actual': 4, 'weight': 400, 'packages': pk, **over}
    r = c.post('/api/receipts', headers=h['mag'], json=body)
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_conform_receipt_sends_green_sheet(env):
    server = mail_env(env)
    rid = receipt(env)
    assert server.process_mail_outbox() == 1
    m = server.MAIL_SENT[0]
    assert m['to'] == ['christophe@taftrans.fr'] and 'Réception conforme' in m['subject'] and 'LTA 057-11112222' in m['subject'] and rid in m['subject']
    name, pdf = m['attachments'][0]
    assert name == f'fiche-reception-{rid}.pdf'
    t = pdf_text(pdf)
    assert 'RÉCEPTION CONFORME' in t and 'Palette 1/2' in t.replace('Palette  1/2', 'Palette 1/2')
    out = env['c'].get('/api/mail-outbox', headers=env['h']['expl']).json()
    assert out[0]['status'] == 'sent' and out[0]['recipients'] == ['christophe@taftrans.fr']
    assert server.process_mail_outbox() == 0                                        # pas de doublon


def test_problem_receipt_and_later_discrepancy(env):
    server = mail_env(env)
    rid = receipt(env, actual=3, expected=4, security_status='a_controler',
                  packages=[{'kind': 'palette', 'length_cm': 120, 'width_cm': 80, 'height_cm': 150, 'weight_kg': 400, 'packages': 3}])
    server.process_mail_outbox()
    m = server.MAIL_SENT[-1]
    assert 'PROBLÈME DE RÉCEPTION' in m['subject'] and 'Colis reçus (3) différents des colis attendus (4)' in m['text'] and 'Sûreté' in m['text']
    assert 'PROBLÈME DE RÉCEPTION' in pdf_text(m['attachments'][0][1])
    ok = receipt(env)
    server.process_mail_outbox()
    env['c'].post(f'/api/receipts/{ok}/discrepancy', headers=env['h']['mag'], json={'kind': 'damage', 'description': 'Palette 2 film déchiré'})
    assert server.process_mail_outbox() == 1
    m = server.MAIL_SENT[-1]
    assert ok in m['subject'] and 'PROBLÈME' in m['subject'] and 'Palette 2 film déchiré' in m['text']


def test_routes_isolation_and_failures(env):
    c, h = env['c'], env['h']
    server = mail_env(env)
    assert c.put('/api/mail-routes/Afrique', headers=h['expl'], json={'recipients': ['x@taftrans.fr']}).status_code == 403
    assert c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['pas-une-adresse']}).status_code == 400
    routes = {r['warehouse']: r['recipients'] for r in c.get('/api/mail-routes', headers=h['resp']).json()['routes']}
    assert routes['Afrique'] == ['christophe@taftrans.fr'] and set(routes) == {'Afrique', 'Maritime', 'Moyen-Orient', 'TMS'}
    # Pas de destinataire : rien n'est programmé.
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': []})
    receipt(env)
    assert c.get('/api/mail-outbox', headers=h['expl']).json() == []
    c.put('/api/mail-routes/Afrique', headers=h['admin'], json={'recipients': ['christophe@taftrans.fr']})
    # Échec d'envoi : retenté, puis abandon signalé après 5 essais.
    rid = receipt(env)
    real = server.send_mail
    server.send_mail = lambda *a: (_ for _ in ()).throw(RuntimeError('SES indisponible'))
    try:
        for _ in range(5):
            with server.db() as db:
                db.execute("UPDATE mail_outbox SET not_before='2000-01-01' WHERE status='pending'")
            server.process_mail_outbox()
    finally:
        server.send_mail = real
    row = c.get('/api/mail-outbox', headers=h['expl']).json()[0]
    assert row['status'] == 'failed' and row['attempts'] == 5 and 'SES indisponible' in row['last_error']
    assert any(n['title'] == 'E-mail non envoyé' for n in c.get('/api/notifications', headers=h['expl']).json())
    # Envoi manuel immédiat ; Maritime ne voit pas la file Afrique.
    assert c.post(f'/api/receipts/{rid}/email', headers=h['mag']).status_code == 403
    assert c.post(f'/api/receipts/{rid}/email', headers=h['expl']).status_code == 200
    assert server.MAIL_SENT and rid in server.MAIL_SENT[-1]['subject']
    assert c.get('/api/mail-outbox', headers=h['expl_mar']).json() == []


def test_receipt_report_download(env):
    rid = receipt(env)
    r = env['c'].get(f'/api/receipts/{rid}/report', headers=env['h']['mag'])
    assert r.status_code == 200 and 'FICHE DE RÉCEPTION' in pdf_text(r.content).upper()
    assert env['c'].get(f'/api/receipts/{rid}/report', headers=env['h']['mag_mar']).status_code == 403
