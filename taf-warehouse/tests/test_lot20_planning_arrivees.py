"""Lot 20 : planning des arrivées partagé exploitation / magasin."""


def arr(env, who='expl', **over):
    c, h = env['c'], env['h']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    body = {'warehouse': 'Afrique', 'planned_date': '2026-11-10', 'reference': '26/02078', 'client_id': cl, 'pickup_name': 'ATI EXPORT',
            'pickup_address': '71240 La Salle', 'carrier': 'Global Transport and Supply', 'packages': 2, 'weight': 485, 'dimensions': '120x80x150, 120x80x118',
            'designation': 'Palettes — Ouagadougou', 'client_ref': 'SF-55277849-1', **over}
    return c.post('/api/arrivals', headers=h[who], json=body)


def test_create_list_and_isolation(env):
    c, h = env['c'], env['h']
    assert arr(env, who='mag').status_code == 403                                   # l'exploitation planifie
    r = arr(env)
    assert r.status_code == 200, r.text
    aid = r.json()['id']
    rows = c.get('/api/arrivals', headers=h['mag'], params={'start': '2026-11-09', 'end': '2026-11-13'}).json()
    assert [x['id'] for x in rows] == [aid] and rows[0]['client'] and rows[0]['packages'] == 2
    assert c.get('/api/arrivals', headers=h['mag'], params={'start': '2026-11-16', 'end': '2026-11-20'}).json() == []
    assert c.get('/api/arrivals', headers=h['mag_mar']).json() == []                # autre entrepôt
    assert c.get(f'/api/arrivals/{aid}', headers=h['mag_mar']).status_code == 403
    assert any(n['ref'] == aid for n in c.get('/api/notifications', headers=h['mag']).json())   # le magasin est prévenu


def test_container_with_time_slot(env):
    c, h = env['c'], env['h']
    assert arr(env, kind='conteneur', container_no='MSC123').status_code == 400
    assert arr(env, kind='conteneur', container_no='mscu 1234567', container_size='40HC', slot_start='14:00', slot_end='13:00').status_code == 400
    r = arr(env, kind='conteneur', container_no='mscu 1234567', container_size='40HC', seal_no='SL998877', slot_start='08:00', slot_end='10:00', dock='Quai 2')
    assert r.status_code == 200, r.text
    a = c.get(f"/api/arrivals/{r.json()['id']}", headers=h['mag']).json()
    assert (a['container_no'], a['container_size'], a['slot_start'], a['slot_end'], a['dock']) == ('MSCU1234567', '40HC', '08:00', '10:00', 'Quai 2')


def test_drag_and_drop_move_and_history(env):
    c, h = env['c'], env['h']
    aid = arr(env).json()['id']
    r = c.post(f'/api/arrivals/{aid}/move', headers=h['mag'], json={'planned_date': '2026-11-12', 'reason': 'Retard transporteur'})
    assert r.status_code == 200                                                     # le magasin peut signaler un retard
    assert c.post(f'/api/arrivals/{aid}/move', headers=h['expl'], json={'planned_date': None}).status_code == 200   # « À venir »
    rows = c.get('/api/arrivals', headers=h['mag'], params={'start': '2026-11-09', 'end': '2026-11-13'}).json()
    assert rows[0]['planned_date'] is None
    hist = c.get(f'/api/arrivals/{aid}', headers=h['mag']).json()['history']
    moves = [e['details'] for e in hist if e['action'] == 'arrival_move']
    first = next(m for m in moves if m['reason'] == 'Retard transporteur')
    assert first['from'] == '2026-11-10' and first['to'] == '2026-11-12' and len(moves) == 2
    assert any(n['title'].startswith('Arrivée retardée') for n in c.get('/api/notifications', headers=h['expl']).json())
    assert c.post(f'/api/arrivals/{aid}/move', headers=h['mag_mar'], json={'planned_date': '2026-11-13'}).status_code == 403


def test_late_and_reception_link(env):
    c, h = env['c'], env['h']
    aid = arr(env, planned_date='2020-01-06').json()['id']
    rows = c.get('/api/arrivals', headers=h['mag'], params={'start': '2026-11-09', 'end': '2026-11-13'}).json()
    assert rows[0]['id'] == aid and rows[0]['late'] is True                          # en retard : reste visible
    cl = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    r = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 2, 'actual': 2, 'weight': 485, 'arrival_id': aid})
    assert r.status_code == 200, r.text
    a = c.get(f'/api/arrivals/{aid}', headers=h['mag']).json()
    assert a['status'] == 'received' and a['receipt_id'] == r.json()['id']
    assert c.post(f'/api/arrivals/{aid}/move', headers=h['expl'], json={'planned_date': '2026-11-12'}).status_code == 409
    r = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 1, 'arrival_id': aid})
    assert r.status_code == 409                                                     # déjà réceptionnée


def test_cancel_and_edit(env):
    c, h = env['c'], env['h']
    aid = arr(env).json()['id']
    cl = c.get('/api/clients', headers=h['admin']).json()[0]['id']
    r = c.put(f'/api/arrivals/{aid}', headers=h['expl'], json={'warehouse': 'Afrique', 'planned_date': '2026-11-10', 'reference': '26/02078', 'client_id': cl, 'packages': 3, 'designation': 'x'})
    assert r.status_code == 200
    assert c.post(f'/api/arrivals/{aid}/cancel', headers=h['mag'], json={'reason': 'Annulé'}).status_code == 403
    assert c.post(f'/api/arrivals/{aid}/cancel', headers=h['expl'], json={'reason': 'Annulé par le client'}).status_code == 200
    assert c.get('/api/arrivals', headers=h['mag']).json() == []


def test_today_arrivals_on_dashboard(env):
    from datetime import datetime, timezone
    c, h, server = env['c'], env['h'], env['server']
    today = server.paris(server.now()).date().isoformat()
    a1 = arr(env, planned_date=today, slot_start='08:00', slot_end='10:00', kind='conteneur', container_no='MSCU1234567').json()['id']
    a2 = arr(env, planned_date='2020-01-06').json()['id']                         # en retard
    arr(env, planned_date='2099-01-05')                                            # plus tard : absent
    d = c.get('/api/dashboard/ops', headers=h['mag'], params={'warehouse': 'Afrique'}).json()
    ids = [x['id'] for x in d['arrivals_today']]
    assert ids == [a2, a1] and d['arrivals_today'][0]['late'] is True and d['arrivals_today'][1]['slot_start'] == '08:00'
    assert c.get('/api/dashboard/ops', headers=h['expl_mar']).json()['arrivals_today'] == []


def test_tv_screen_link(env):
    c, h, server = env['c'], env['h'], env['server']
    today = server.paris(server.now()).date().isoformat()
    arr(env, planned_date=today, slot_start='08:00', slot_end='10:00', kind='conteneur', container_no='MSCU1234567')
    assert c.post('/api/tv-screens', headers=h['mag'], json={'name': 'TV', 'warehouses': ['Afrique']}).status_code == 403
    assert c.post('/api/tv-screens', headers=h['resp'], json={'name': 'TV', 'warehouses': ['Maritime']}).status_code == 403
    r = c.post('/api/tv-screens', headers=h['resp'], json={'name': 'TV exploitation', 'warehouses': ['Afrique']})
    assert r.status_code == 200 and r.json()['path'].startswith('/tv.html#k=')
    tok, sid = r.json()['token'], r.json()['id']
    assert c.get('/api/tv/data').status_code == 401
    assert c.get('/api/tv/data', headers={'X-TV-Token': 'faux'}).status_code == 401
    d = c.get('/api/tv/data', headers={'X-TV-Token': tok}).json()
    assert d['screen'] == 'TV exploitation' and d['warehouses'] == ['Afrique'] and len(d['week']) == 6
    assert d['arrivals_today'][0]['container_no'] == 'MSCU1234567' and 'kpis' in d and 'exits_today' in d
    assert 'driver' not in str(d).lower()                                           # aucune donnée de chauffeur
    rows = c.get('/api/tv-screens', headers=h['resp']).json()
    assert rows[0]['last_seen'] and 'token' not in rows[0]
    assert c.post(f'/api/tv-screens/{sid}/revoke', headers=h['resp']).status_code == 200
    assert c.get('/api/tv/data', headers={'X-TV-Token': tok}).status_code == 401
    assert c.get('/tv.html').status_code == 200


def test_tv_inside_application(env):
    c, h = env['c'], env['h']
    d = c.get('/api/tv/me', headers=h['mag']).json()
    assert d['warehouses'] == ['Afrique'] and 'kpis' in d
    assert c.get('/api/tv/me', headers=h['mag'], params={'warehouse': 'Maritime'}).status_code == 403
    assert c.get('/api/tv/me').status_code == 401
