"""Connexion par prénom + code PIN pour les magasiniers et chefs d'équipe (sans adresse e-mail)."""
import importlib, time
import pytest
from fastapi.testclient import TestClient
from conftest import PWD


def create(env, name, role='worker', **secret):
    body = {'username': name, 'role': role, 'warehouses': ['Afrique'], **secret}
    return env['c'].post('/api/users', headers=env['h']['admin'], json=body)


def login(env, name, secret, **extra):
    return env['c'].post('/api/login', json={'username': name, 'password': secret, **extra})


def test_worker_logs_in_with_first_name_and_pin(env):
    assert create(env, 'Mamadou', pin='482915').status_code == 200
    r = login(env, 'mamadou', '482915')
    assert r.status_code == 200, r.text
    assert r.json()['user']['role'] == 'worker' and r.json()['mfa_setup_required'] is False
    h = {'Authorization': 'Bearer ' + r.json()['token']}
    assert env['c'].get('/api/units', headers=h).status_code == 200
    row = next(u for u in env['c'].get('/api/users', headers=env['h']['admin']).json() if u['username'] == 'mamadou')
    assert row['auth_mode'] == 'pin'


def test_pin_only_for_floor_roles(env):
    assert create(env, 'fatou', role='exploitation', pin='482915').status_code == 400
    assert create(env, 'ibrahim', role='leader', pin='731904').status_code == 200
    assert create(env, 'awa', role='worker').status_code == 400  # ni mot de passe ni PIN
    assert create(env, 'awa', role='worker', pin='482915', password=PWD).status_code == 400  # l'un ou l'autre


@pytest.mark.parametrize('pin', ['123456', '000000', '111111', '654321', '12345', '1234567', '12a456', '123123'])
def test_weak_or_malformed_pins_rejected(env, pin):
    assert create(env, 'moussa', pin=pin).status_code in (400, 422)


def test_wrong_pin_locks_account(env):
    create(env, 'aminata', pin='482915')
    for _ in range(5):
        assert login(env, 'aminata', '000001').status_code == 401
    assert login(env, 'aminata', '482915').status_code == 429


def test_superadmin_resets_pin_and_role_change_rules(env):
    c, h = env['c'], env['h']
    create(env, 'oumar', pin='482915')
    oid = next(u['id'] for u in c.get('/api/users', headers=h['admin']).json() if u['username'] == 'oumar')
    assert c.post(f'/api/users/{oid}/reset-pin', headers=h['admin'], json={'pin': '903174'}).status_code == 200
    assert login(env, 'oumar', '482915').status_code == 401
    assert login(env, 'oumar', '903174').status_code == 200
    assert c.post(f'/api/users/{oid}/reset-pin', headers=h['resp'], json={'pin': '903175'}).status_code == 403
    # Un compte PIN ne peut pas recevoir un rôle sensible sans mot de passe.
    assert c.put(f'/api/users/{oid}', headers=h['admin'], json={'role': 'exploitation', 'warehouses': ['Afrique']}).status_code == 400
    assert c.put(f'/api/users/{oid}', headers=h['admin'], json={'role': 'leader', 'warehouses': ['Afrique']}).status_code == 200
    # PIN refusé sur un compte à mot de passe.
    mag = next(u['id'] for u in c.get('/api/users', headers=h['admin']).json() if u['username'] == 'mag')
    assert c.post(f'/api/users/{mag}/reset-pin', headers=h['admin'], json={'pin': '903174'}).status_code == 400


def test_user_changes_own_pin(env):
    c = env['c']
    create(env, 'kadiatou', pin='482915')
    h = {'Authorization': 'Bearer ' + login(env, 'kadiatou', '482915').json()['token']}
    assert c.post('/api/pin', headers=h, json={'old': '000000', 'new': '736291'}).status_code == 403
    assert c.post('/api/pin', headers=h, json={'old': '482915', 'new': '123456'}).status_code == 400
    assert c.post('/api/pin', headers=h, json={'old': '482915', 'new': '736291'}).status_code == 200
    assert login(env, 'kadiatou', '736291').status_code == 200


def test_mfa_account_asked_for_code_without_counting_a_failure(env):
    """Sans code, un compte à double authentification reçoit une demande explicite, pas un échec."""
    c, server = env['c'], env['server']
    h = env['h']['expl']
    setup = c.post('/api/mfa/setup', headers=h).json()
    code = server.totp(setup['secret'], int(time.time()) // 30)
    assert c.post('/api/mfa/confirm', headers=h, json={'otp': code}).status_code == 200
    for _ in range(6):
        r = login(env, 'expl', PWD)
        assert r.status_code == 401 and r.json()['detail'] == 'Code de double authentification requis'
    code = server.totp(setup['secret'], int(time.time()) // 30 + 1)
    assert login(env, 'expl', PWD, otp=code).status_code == 200  # pas de verrouillage
