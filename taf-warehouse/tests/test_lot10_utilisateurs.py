"""Gestion des utilisateurs par le Super Admin : créer, modifier (rôle, entrepôts), supprimer (archiver)."""
from conftest import PWD


def uid_of(env, name):
    return next(u['id'] for u in env['c'].get('/api/users', headers=env['h']['admin']).json() if u['username'] == name)


def login(env, name):
    return env['c'].post('/api/login', json={'username': name, 'password': PWD})


def test_superadmin_changes_role_and_warehouses(env):
    c, h = env['c'], env['h']
    mag = uid_of(env, 'mag')
    r = c.put(f'/api/users/{mag}', headers=h['admin'], json={'role': 'leader', 'warehouses': ['Afrique', 'Maritime']})
    assert r.status_code == 200, r.text
    row = next(u for u in c.get('/api/users', headers=h['admin']).json() if u['id'] == mag)
    assert row['role'] == 'leader' and row['warehouses'] == ['Afrique', 'Maritime']
    assert c.get('/api/me', headers=h['mag']).status_code == 401  # sessions fermées : nouveaux droits à la reconnexion
    assert any(a['action'] == 'user_update' and a['ref'] == mag for a in c.get('/api/audit', headers=h['admin']).json())


def test_only_superadmin_manages_users(env):
    c, h = env['c'], env['h']
    mag = uid_of(env, 'mag')
    assert c.put(f'/api/users/{mag}', headers=h['resp'], json={'role': 'admin', 'warehouses': ['Afrique']}).status_code == 403
    assert c.delete(f'/api/users/{mag}', headers=h['expl']).status_code == 403
    assert c.post('/api/users', headers=h['resp'], json={'username': 'x1', 'password': PWD, 'role': 'worker', 'warehouses': ['Afrique']}).status_code == 403


def test_invalid_updates_rejected(env):
    c, h = env['c'], env['h']
    mag = uid_of(env, 'mag')
    assert c.put(f'/api/users/{mag}', headers=h['admin'], json={'role': 'chef', 'warehouses': ['Afrique']}).status_code == 400
    assert c.put(f'/api/users/{mag}', headers=h['admin'], json={'role': 'worker', 'warehouses': []}).status_code == 400
    assert c.put(f'/api/users/{mag}', headers=h['admin'], json={'role': 'worker', 'warehouses': ['Lune']}).status_code == 400
    me = uid_of(env, 'admin')
    assert c.put(f'/api/users/{me}', headers=h['admin'], json={'role': 'worker', 'warehouses': ['Afrique']}).status_code == 400


def test_delete_archives_account_and_keeps_history(env):
    c, h = env['c'], env['h']
    mag = uid_of(env, 'mag')
    rec = env['receipt']()  # action tracée au nom de « mag »
    r = c.delete(f'/api/users/{mag}', headers=h['admin'])
    assert r.status_code == 200, r.text
    assert 'mag' not in [u['username'] for u in c.get('/api/users', headers=h['admin']).json()]
    assert 'mag' in [u['username'] for u in c.get('/api/users', params={'include_deleted': 'true'}, headers=h['admin']).json()]
    assert login(env, 'mag').status_code == 401
    assert c.get('/api/me', headers=h['mag']).status_code == 401
    assert any(a['actor'] == 'mag' and a['ref'] == rec for a in c.get('/api/audit', headers=h['admin']).json())
    # L'identifiant reste réservé : pas de confusion dans l'historique.
    assert c.post('/api/users', headers=h['admin'], json={'username': 'mag', 'password': PWD, 'role': 'worker', 'warehouses': ['Afrique']}).status_code == 409
    assert c.post(f'/api/users/{mag}/status', headers=h['admin'], json={'active': True}).status_code == 409


def test_cannot_delete_self_or_last_superadmin(env):
    c, h = env['c'], env['h']
    me = uid_of(env, 'admin')
    assert c.delete(f'/api/users/{me}', headers=h['admin']).status_code == 400
    # Un autre Super Admin peut archiver ce compte ; comme personne ne peut se supprimer soi-même, il reste toujours un Super Admin actif.
    assert c.post('/api/users', headers=h['admin'], json={'username': 'christophe', 'password': PWD, 'role': 'superadmin', 'warehouses': ['Afrique', 'Maritime', 'Moyen-Orient', 'TMS']}).status_code == 200
    ch = {'Authorization': 'Bearer ' + login(env, 'christophe').json()['token']}
    christophe = uid_of(env, 'christophe')
    assert c.delete(f'/api/users/{me}', headers=ch).status_code == 200
    # La session de l'admin archivé est révoquée : il ne peut plus rien modifier.
    assert c.put(f'/api/users/{christophe}', headers=h['admin'], json={'role': 'admin', 'warehouses': ['Afrique']}).status_code == 401
