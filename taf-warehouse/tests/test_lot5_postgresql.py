"""Lot 5 — moteur de base : le même code tourne sur SQLite (local) et PostgreSQL (serveur)."""
import os
import pytest


def test_engine_matches_configuration(env):
    health = env['c'].get('/api/health', headers=env['h']['admin']).json()
    expected = 'postgresql' if os.getenv('TAF_TEST_DATABASE_URL') else 'sqlite'
    assert health['engine'] == expected and health['database'] == 'ok'


def test_decimal_free_and_typed_results(env):
    """Les agrégats PostgreSQL (numeric) sont rendus en nombres JSON ordinaires."""
    rec = env['receipt']()
    env['unit'](rec, quantity=2, weight=12.5)
    dash = env['c'].get('/api/dashboard', headers=env['h']['admin']).json()
    assert dash['units'] == {'n': 1, 'quantity': 2}
    u = env['c'].get('/api/units', headers=env['h']['admin']).json()[0]
    assert u['weight'] == pytest.approx(12.5) and isinstance(u['quantity'], int)


def test_no_sqlite_only_sql_left_in_server():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'app', 'server.py'), encoding='utf-8').read()
    for forbidden in ('INSERT OR IGNORE', 'INSERT OR REPLACE', '="available"', 'IN ("'):
        assert forbidden not in src, forbidden


@pytest.mark.skipif(not os.getenv('TAF_TEST_DATABASE_URL'), reason='PostgreSQL de test non configuré')
def test_sqlite_to_postgresql_migration(tmp_path, monkeypatch):
    """Une base SQLite remplie (V4.4 + lots) est copiée à l'identique et l'application repart dessus."""
    import importlib, uuid, psycopg
    from fastapi.testclient import TestClient
    from helpers import signature
    pg_url = os.environ['TAF_DATABASE_URL']
    # 1. Activité réelle sur SQLite.
    monkeypatch.delenv('TAF_DATABASE_URL')
    monkeypatch.setenv('TAF_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TAF_ADMIN_PASSWORD', 'TestPassword12345!')
    from app import server
    importlib.reload(server)
    assert not server.PG
    c = TestClient(server.app)
    h = {'Authorization': 'Bearer ' + c.post('/api/login', json={'username': 'admin', 'password': 'TestPassword12345!'}).json()['token']}
    cl = c.get('/api/clients', headers=h).json()[0]['id']
    rec = c.post('/api/receipts', headers=h, json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 3, 'actual': 2, 'weight': 50}).json()['id']
    unit = c.post('/api/units', headers=h, json={'receipt_id': rec, 'description': 'Palette', 'quantity': 2, 'weight': 50.5}).json()['id']
    c.post('/api/incidents', headers=h, json={'warehouse': 'Afrique', 'unit_id': unit, 'category': 'damage', 'severity': 'major', 'description': 'Film déchiré'})
    c.post(f'/api/documents/receipt/{rec}', headers=h, files={'file': ('bl.pdf', b'%PDF-1.4 bon', 'application/pdf')})
    before = {k: c.get('/api/' + k, headers=h).json() for k in ('units', 'receipts', 'incidents', 'audit')}
    # 2. Migration vers le schéma PostgreSQL du test.
    monkeypatch.setenv('TAF_DATABASE_URL', pg_url)
    from app import migrate_pg
    report = migrate_pg.migrate(str(tmp_path / 'warehouse.sqlite3'))
    assert report['units'] == 1 and report['unit_holds'] == 2 and report['audit'] >= 5
    with pytest.raises(SystemExit):
        migrate_pg.migrate(str(tmp_path / 'warehouse.sqlite3'))  # cible non vide : refus
    # 3. L'application repart sur PostgreSQL avec les mêmes comptes et données.
    assert 'TAF_SKIP_BOOTSTRAP' not in os.environ
    importlib.reload(server)
    assert server.PG
    c = TestClient(server.app)
    h = {'Authorization': 'Bearer ' + c.post('/api/login', json={'username': 'admin', 'password': 'TestPassword12345!'}).json()['token']}
    after = {k: c.get('/api/' + k, headers=h).json() for k in ('units', 'receipts', 'incidents')}
    assert after == {k: before[k] for k in after}
    assert len(c.get('/api/audit', headers=h).json()) >= len(before['audit'])
    assert len(c.get('/api/units/' + unit + '/holds', headers=h).json()) == 2
