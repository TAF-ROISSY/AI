"""Missions (types, affectation, cycle de vie, retards, charge) et tableau de bord opérationnel."""
from helpers import putaway


def mission(env, who='expl', **over):
    body = {'warehouse': 'Afrique', 'type': 'rangement', 'title': 'Ranger la réception du matin', 'assignee': 'mag', 'priority': 'high', 'due_at': '2030-01-01T10:00', **over}
    return env['c'].post('/api/missions', headers=env['h'][who], json=body)


def get(env, mid):
    return next(m for m in env['c'].get('/api/missions', headers=env['h']['expl']).json() if m['id'] == mid)


def act(env, mid, action, who='mag', note='Suivi'):
    return env['c'].post(f'/api/missions/{mid}/status', headers=env['h'][who], json={'action': action, 'note': note})


def test_mission_lifecycle(env):
    r = mission(env)
    assert r.status_code == 200, r.text
    mid = r.json()['id']
    m = get(env, mid)
    assert (m['type'], m['assignee'], m['status'], m['priority']) == ('rangement', 'mag', 'assigned', 'high')
    assert act(env, mid, 'start').status_code == 200 and get(env, mid)['status'] == 'in_progress'
    assert act(env, mid, 'suspend', note='x').status_code == 400          # motif obligatoire
    assert act(env, mid, 'suspend', note='Attente chariot élévateur').status_code == 200 and get(env, mid)['status'] == 'suspended'
    assert act(env, mid, 'resume').status_code == 200
    assert act(env, mid, 'complete', note='Réception rangée').status_code == 200
    m = get(env, mid)
    assert m['status'] == 'done' and m['completed_by'] == 'mag' and [e['action'] for e in m['events']] == ['start', 'suspend', 'resume', 'complete']
    assert act(env, mid, 'start').status_code == 409


def test_mission_rules(env):
    assert mission(env, who='mag').status_code == 403
    assert mission(env, type='peinture').status_code == 422
    assert mission(env, assignee='mag_mar').status_code == 400               # pas habilité Afrique
    r = mission(env, assignee='')
    assert r.status_code == 200 and get(env, r.json()['id'])['status'] == 'to_assign'
    mid = mission(env).json()['id']
    assert act(env, mid, 'start', who='mag_mar').status_code == 403
    assert act(env, mid, 'start', who='expl2').status_code == 403            # affectée à un autre
    assert act(env, mid, 'cancel', who='mag', note='Plus nécessaire').status_code == 403  # annulation : bureau
    assert act(env, mid, 'cancel', who='expl', note='Plus nécessaire').status_code == 200
    assert env['c'].post(f'/api/missions/{mid}/assign', headers=env['h']['expl'], json={'assignee': 'mag'}).status_code == 409


def test_reassign_and_late_and_workload(env):
    c, h = env['c'], env['h']
    late = mission(env, due_at='2020-01-01T08:00', assignee='').json()['id']
    assert c.post(f'/api/missions/{late}/assign', headers=h['expl'], json={'assignee': 'mag'}).status_code == 200
    mission(env, title='Préparer DOS-1', type='preparation')
    m = get(env, late)
    assert m['status'] == 'assigned' and m['late'] is True
    dash = c.get('/api/dashboard/ops', headers=h['expl']).json()
    assert dash['kpis']['missions_late'] == 1
    load = {x['assignee']: x for x in dash['workload']}
    assert load['mag']['open'] == 2 and load['mag']['late'] == 1


def test_dashboard_kpis_and_alerts_reflect_real_data(env):
    c, h, server = env['c'], env['h'], env['server']
    rec = env['receipt'](expected=8, actual=8)
    placed = env['unit'](rec, quantity=4, weight=400).json()['id']                     # rangée (zone temporaire)
    waiting = env['unit'](rec, quantity=4, weight=300, placed=False).json()['id']      # à ranger
    with server.db() as db:
        db.execute("UPDATE movements SET at='2020-01-01T00:00:00+00:00' WHERE unit_id=? AND kind='receive'", (waiting,))
    c.post('/api/incidents', headers=h['mag'], json={'warehouse': 'Afrique', 'unit_id': placed, 'category': 'damage', 'severity': 'major', 'description': 'Film déchiré'})
    oid = c.post('/api/release-orders', headers=h['expl'], json={'warehouse': 'Afrique', 'reference': 'DOS-9', 'lines': [{'unit_id': placed, 'quantity': 1}]})
    dash = c.get('/api/dashboard/ops', headers=h['expl'], params={'warehouse': 'Afrique'}).json()
    k = dash['kpis']
    assert k['receipts_today'] == 1 and k['units_present'] == 2 and k['packages_present'] == 8 and k['weight_kg'] == 700
    assert k['awaiting_putaway'] == 1 and k['incidents_open'] == 1 and k['held_units'] == 1
    codes = {a['code']: a for a in dash['alerts']}
    assert 'putaway_late' in codes and waiting in codes['putaway_late']['refs']
    assert 'incident_no_owner' in codes
    assert oid.status_code == 400  # unité bloquée par l'incident : pas d'ordre de sortie
    assert dash['activity'] and any(a['actor'] == 'mag' for a in dash['activity'])
    # Isolation : Maritime ne voit rien d'Afrique.
    assert c.get('/api/dashboard/ops', headers=h['expl_mar']).json()['kpis']['units_present'] == 0
    assert c.get('/api/dashboard/ops', headers=h['expl_mar'], params={'warehouse': 'Afrique'}).status_code == 403
