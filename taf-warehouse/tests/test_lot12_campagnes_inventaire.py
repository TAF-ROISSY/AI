"""Inventaires par campagne : périmètre, affectation, comptage, écarts, validation indépendante, clôture et rapport."""
import io
from pypdf import PdfReader
from helpers import putaway


def stock(env, n=3, location='AFR-TEMP'):
    rec = env['receipt'](expected=4 * n, actual=4 * n)
    ids = [env['unit'](rec, quantity=4, weight=400, placed=False).json()['id'] for _ in range(n)]
    for u in ids:
        putaway(env['server'], u, location)
    return ids


def campaign(env, who='expl', **body):
    payload = {'warehouse': 'Afrique', 'scope': 'location', 'value': 'AFR-TEMP', 'assignee': 'mag', 'title': 'Inventaire zone temporaire', **body}
    return env['c'].post('/api/inventory-campaigns', headers=env['h'][who], json=payload)


def get(env, cid):
    return next(x for x in env['c'].get('/api/inventory-campaigns', headers=env['h']['expl']).json() if x['id'] == cid)


def count(env, cid, unit, observed, who='mag'):
    return env['c'].post(f'/api/inventory-campaigns/{cid}/count', headers=env['h'][who], json={'unit_id': unit, 'observed': observed})


def test_campaign_lists_scope_and_conform_counts_close(env):
    ids = stock(env)
    r = campaign(env)
    assert r.status_code == 200, r.text
    cid = r.json()['id']
    camp = get(env, cid)
    assert camp['status'] == 'open' and {i['unit_id'] for i in camp['items']} == set(ids) and camp['progress'] == {'total': 3, 'counted': 0, 'discrepancies': 0}
    for u in ids:
        assert count(env, cid, u, 4).status_code == 200
    camp = get(env, cid)
    assert camp['progress'] == {'total': 3, 'counted': 3, 'discrepancies': 0}
    assert all(i['result'] == 'conforme' for i in camp['items'])
    assert env['c'].post(f'/api/inventory-campaigns/{cid}/close', headers=env['h']['expl'], json={'note': 'Zone conforme'}).status_code == 200
    assert get(env, cid)['status'] == 'closed'
    pdf = env['c'].get(f'/api/inventory-campaigns/{cid}/report', headers=env['h']['expl'])
    assert pdf.status_code == 200
    text = ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert 'INVENTAIRE' in text.upper() and cid in text and 'conforme' in text.lower()


def test_discrepancy_needs_recount_and_independent_validation(env):
    c, h = env['c'], env['h']
    ids = stock(env, n=2)
    cid = campaign(env).json()['id']
    assert count(env, cid, ids[0], 4).status_code == 200
    r = count(env, cid, ids[1], 3)
    assert r.status_code == 200 and r.json()['result'] == 'ecart'
    camp = get(env, cid)
    item = next(i for i in camp['items'] if i['unit_id'] == ids[1])
    assert camp['progress']['discrepancies'] == 1 and item['count_id']
    # Stock inchangé tant que l'écart n'est pas validé ; clôture impossible.
    assert next(u for u in c.get('/api/units', headers=h['admin']).json() if u['id'] == ids[1])['quantity'] == 4
    assert c.post(f'/api/inventory-campaigns/{cid}/close', headers=h['expl'], json={'note': 'x clôture'}).status_code == 409
    # Circuit existant : recomptage par une autre personne puis validation par une troisième.
    assert c.post(f"/api/counts/{item['count_id']}/recount", headers=h['expl2'], json={'observed': 3}).status_code == 200
    assert c.post(f"/api/counts/{item['count_id']}/review", headers=h['expl'], json={'approve': True, 'reason': 'Un colis manquant confirmé'}).status_code == 200
    assert next(u for u in c.get('/api/units', headers=h['admin']).json() if u['id'] == ids[1])['quantity'] == 3
    assert c.post(f'/api/inventory-campaigns/{cid}/close', headers=h['expl'], json={'note': 'Écart traité'}).status_code == 200


def test_rules(env):
    c, h = env['c'], env['h']
    ids = stock(env, n=1)
    assert campaign(env, who='mag').status_code == 403
    assert campaign(env, assignee='personne').status_code == 400
    assert campaign(env, assignee='mag_mar').status_code == 400       # pas habilité Afrique
    assert campaign(env, value='AFR-R09-Z9').status_code == 400       # emplacement sans stock
    cid = campaign(env).json()['id']
    assert campaign(env).status_code == 409                           # unité déjà dans une campagne ouverte
    assert count(env, cid, ids[0], 4, who='mag_mar').status_code == 403  # pas l'affecté
    assert count(env, cid, ids[0], 4).status_code == 200
    assert count(env, cid, ids[0], 4).status_code == 409              # déjà comptée
    assert count(env, cid, 'UNIT-INCONNUE', 1).status_code == 404


def test_rack_and_warehouse_scopes(env):
    a = stock(env, n=1, location='AFR-TEMP')
    b = stock(env, n=2, location='AFR-R01-A1')
    r = campaign(env, scope='rack', value='AFR-R01')
    assert r.status_code == 200, r.text
    assert {i['unit_id'] for i in get(env, r.json()['id'])['items']} == set(b)
    env['c'].post(f"/api/inventory-campaigns/{r.json()['id']}/cancel", headers=env['h']['expl'], json={'note': 'Erreur de périmètre'})
    w = campaign(env, scope='warehouse', value=None)
    assert {i['unit_id'] for i in get(env, w.json()['id'])['items']} == set(a + b)
