"""Lot 6 — prêt pour AWS : stockage S3 privé, Secrets Manager, mode production, double authentification obligatoire.

AWS est simulé localement (moto) : aucun appel réseau, aucune ressource réelle.
"""
import base64, hashlib, importlib, json, os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from helpers import signature, putaway, png_bytes

BUCKET = 'taf-warehouse-documents-test'
PWD = 'TestPassword12345!'


@pytest.fixture
def aws(monkeypatch):
    for k, v in {'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing', 'AWS_SESSION_TOKEN': 'testing',
                 'AWS_DEFAULT_REGION': 'eu-west-3', 'AWS_REGION': 'eu-west-3'}.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        s3 = boto3.client('s3', region_name='eu-west-3')
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={'LocationConstraint': 'eu-west-3'})
        yield s3


def boot(monkeypatch, tmp_path, **env):
    monkeypatch.setenv('TAF_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TAF_ADMIN_PASSWORD', PWD)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app import server
    importlib.reload(server)
    c = TestClient(server.app)
    return server, c


def login(c, name='admin', **extra):
    r = c.post('/api/login', json={'username': name, 'password': PWD, **extra})
    assert r.status_code == 200, r.text
    return r.json(), {'Authorization': 'Bearer ' + r.json()['token']}


# --- Stockage S3 privé ---

def test_documents_go_to_private_s3_and_downloads_are_audited(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path, TAF_STORAGE='s3', TAF_S3_BUCKET=BUCKET, TAF_S3_PREFIX='documents/')
    _, h = login(c)
    cl = c.get('/api/clients', headers=h).json()[0]['id']
    rec = c.post('/api/receipts', headers=h, json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 1}).json()['id']
    raw = b'%PDF-1.4 bon de livraison'
    r = c.post(f'/api/documents/receipt/{rec}', headers=h, files={'file': ('bl.pdf', raw, 'application/pdf')})
    assert r.status_code == 200, r.text
    did = r.json()['id']
    objects = aws.list_objects_v2(Bucket=BUCKET)['Contents']
    assert [o['Key'] for o in objects] == [f'documents/{did}.pdf']
    head = aws.head_object(Bucket=BUCKET, Key=f'documents/{did}.pdf')
    assert head['ServerSideEncryption'] == 'AES256'
    assert not list((tmp_path / 'uploads').iterdir()), 'aucun fichier sur le disque du serveur'
    dl = c.get(f'/api/documents/{did}/download', headers=h)
    assert dl.status_code == 200 and dl.content == raw
    assert 'attachment' in dl.headers['content-disposition']
    assert any(a['action'] == 'download' and a['ref'] == did for a in c.get('/api/audit', headers=h).json())


def test_s3_object_removed_when_database_write_fails(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path, TAF_STORAGE='s3', TAF_S3_BUCKET=BUCKET)
    _, h = login(c)
    cl = c.get('/api/clients', headers=h).json()[0]['id']
    rec = c.post('/api/receipts', headers=h, json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 1}).json()['id']
    monkeypatch.setattr(server, 'audit', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('panne')))
    broken = TestClient(server.app, raise_server_exceptions=False)
    assert broken.post(f'/api/documents/receipt/{rec}', headers=h, files={'file': ('bl.pdf', b'%PDF-1.4 x', 'application/pdf')}).status_code == 500
    assert aws.list_objects_v2(Bucket=BUCKET).get('KeyCount', 0) == 0


def test_refusal_report_embeds_photo_from_s3(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path, TAF_STORAGE='s3', TAF_S3_BUCKET=BUCKET)
    _, a = login(c)
    for n, r, w in [('expl', 'exploitation', ['Afrique', 'Maritime']), ('expl2', 'exploitation', ['Afrique']), ('mag', 'worker', ['Afrique']), ('magmar', 'worker', ['Maritime']), ('axel', 'manager', ['Maritime'])]:
        c.post('/api/users', headers=a, json={'username': n, 'password': PWD, 'role': r, 'warehouses': w})
    h = {n: login(c, n)[1] for n in ('expl', 'expl2', 'mag', 'magmar', 'axel')}
    cl = c.get('/api/clients', headers=a).json()[0]['id']
    rec = c.post('/api/receipts', headers=h['mag'], json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 10}).json()['id']
    u = c.post('/api/units', headers=h['mag'], json={'receipt_id': rec, 'description': 'Palette', 'quantity': 1, 'weight': 10}).json()['id']
    putaway(server, u)
    tid = c.post('/api/transfers', headers=h['expl'], json={'unit_id': u, 'destination': 'Maritime'}).json()['id']
    c.post(f'/api/transfers/{tid}/approve', headers=h['expl2'])
    drv = c.post('/api/drivers', headers=h['mag'], json={'name': 'Chauffeur'}).json()['id']
    assert c.post(f'/api/transfers/{tid}/dispatch', headers=h['mag'], json={'confirmation': True, 'note': 'Camion test', 'driver_id': drv, 'signature_name': 'Chauffeur', 'signature_data': signature(), 'signature_consent': True}).status_code == 200
    rid = c.post(f'/api/transfers/{tid}/refuse', headers=h['magmar'], json={'reason': 'Palette effondrée à l’arrivée'}).json()['id']
    assert c.post(f'/api/documents/transfer/{tid}', headers=h['magmar'], files={'file': ('p.png', png_bytes(), 'image/png')}).status_code == 200
    r = c.post(f'/api/transfer-refusals/{rid}/review', headers=h['axel'], json={'approve': True, 'note': 'Refus justifié'})
    assert r.status_code == 200, r.text
    pdf = c.get(f"/api/documents/{r.json()['report_document_id']}/download", headers=h['expl']).content
    from pypdf import PdfReader
    reader = PdfReader(__import__('io').BytesIO(pdf))
    assert sum(len(p.images) for p in reader.pages) == 1, 'la photo stockée sur S3 est intégrée au rapport'
    assert aws.list_objects_v2(Bucket=BUCKET)['KeyCount'] == 2


def test_local_files_migrate_to_s3(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path)
    _, h = login(c)
    cl = c.get('/api/clients', headers=h).json()[0]['id']
    rec = c.post('/api/receipts', headers=h, json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 1}).json()['id']
    raw = png_bytes()
    did = c.post(f'/api/documents/receipt/{rec}', headers=h, files={'file': ('photo.png', raw, 'image/png')}).json()['id']
    monkeypatch.setenv('TAF_STORAGE', 's3'); monkeypatch.setenv('TAF_S3_BUCKET', BUCKET)
    importlib.reload(server)
    from app import migrate_files
    report = migrate_files.migrate()
    assert report == {'migrated': 1, 'already_s3': 0}
    assert migrate_files.migrate() == {'migrated': 0, 'already_s3': 1}  # rejouable
    c = TestClient(server.app)
    _, h = login(c)
    assert c.get(f'/api/documents/{did}/download', headers=h).content == raw


def test_migration_detects_corrupted_local_file(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path)
    _, h = login(c)
    cl = c.get('/api/clients', headers=h).json()[0]['id']
    rec = c.post('/api/receipts', headers=h, json={'warehouse': 'Afrique', 'client_id': cl, 'expected': 1, 'actual': 1, 'weight': 1}).json()['id']
    did = c.post(f'/api/documents/receipt/{rec}', headers=h, files={'file': ('bl.pdf', b'%PDF-1.4 original', 'application/pdf')}).json()['id']
    (tmp_path / 'uploads' / f'{did}.pdf').write_bytes(b'%PDF-1.4 altere')
    monkeypatch.setenv('TAF_STORAGE', 's3'); monkeypatch.setenv('TAF_S3_BUCKET', BUCKET)
    importlib.reload(server)
    from app import migrate_files
    with pytest.raises(SystemExit, match='Empreinte'):
        migrate_files.migrate()
    assert aws.list_objects_v2(Bucket=BUCKET).get('KeyCount', 0) == 0


# --- Secrets Manager ---

def test_secrets_loaded_from_secrets_manager(aws, monkeypatch, tmp_path):
    key = base64.urlsafe_b64encode(b'secret-manager-key-for-tests-123').decode()
    arn = boto3.client('secretsmanager', region_name='eu-west-3').create_secret(
        Name='taf-warehouse/app', SecretString=json.dumps({'TAF_MFA_ENCRYPTION_KEY': key, 'TAF_ADMIN_PASSWORD': 'FromSecret12345!'}))['ARN']
    monkeypatch.delenv('TAF_ADMIN_PASSWORD', raising=False)
    monkeypatch.delenv('TAF_MFA_ENCRYPTION_KEY', raising=False)
    monkeypatch.setenv('TAF_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TAF_SECRETS_ARN', arn)
    from app import server
    importlib.reload(server)
    assert os.environ['TAF_MFA_ENCRYPTION_KEY'] == key
    c = TestClient(server.app)
    assert c.post('/api/login', json={'username': 'admin', 'password': 'FromSecret12345!'}).status_code == 200
    assert not (tmp_path / 'INITIAL_ADMIN_PASSWORD.txt').exists()


def test_database_url_built_from_rds_managed_secret(aws, monkeypatch):
    arn = boto3.client('secretsmanager', region_name='eu-west-3').create_secret(
        Name='rds!db-test', SecretString=json.dumps({'username': 'taf_app', 'password': 'p@ss:w/rd'}))['ARN']
    from app import server
    url = server.database_url_from_rds_secret(arn, host='db.internal', port='5432', name='warehouse')
    assert url == 'postgresql://taf_app:p%40ss%3Aw%2Frd@db.internal:5432/warehouse?sslmode=require'


# --- Mode production ---

def test_production_refuses_incomplete_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv('TAF_ENV', 'production')
    monkeypatch.delenv('TAF_DATABASE_URL', raising=False)
    monkeypatch.setenv('TAF_DATA_DIR', str(tmp_path))
    from app import server
    with pytest.raises(RuntimeError) as err:
        importlib.reload(server)
    msg = str(err.value)
    assert 'PostgreSQL' in msg and 'S3' in msg
    monkeypatch.setenv('TAF_ENV', 'test')
    importlib.reload(server)


@pytest.mark.skipif(not os.getenv('TAF_TEST_DATABASE_URL'), reason='PostgreSQL de test non configuré')
def test_production_starts_when_complete_and_hides_api_docs(aws, monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path, TAF_ENV='production', TAF_STORAGE='s3', TAF_S3_BUCKET=BUCKET)
    assert server.PRODUCTION and server.PG
    assert c.get('/docs').status_code == 404 and c.get('/openapi.json').status_code == 404
    data, h = login(c)
    assert data['mfa_setup_required'] is True  # Super Admin : double authentification obligatoire
    assert c.get('/api/units', headers=h).status_code == 403
    monkeypatch.setenv('TAF_ENV', 'test')


# --- Double authentification obligatoire ---

def test_mfa_mandatory_for_configured_roles(monkeypatch, tmp_path):
    server, c = boot(monkeypatch, tmp_path, TAF_MFA_REQUIRED_ROLES='exploitation')
    _, a = login(c)
    for n, r in [('expl', 'exploitation'), ('mag', 'worker')]:
        c.post('/api/users', headers=a, json={'username': n, 'password': PWD, 'role': r, 'warehouses': ['Afrique']})
    _, mag = login(c, 'mag')
    assert c.get('/api/units', headers=mag).status_code == 200  # rôle non concerné
    data, h = login(c, 'expl')
    assert data['mfa_setup_required'] is True
    denied = c.get('/api/units', headers=h)
    assert denied.status_code == 403 and 'Double authentification obligatoire' in denied.json()['detail']
    me = c.get('/api/me', headers=h).json()
    assert me['mfa_required'] is True and me['mfa_enabled'] is False
    setup = c.post('/api/mfa/setup', headers=h).json()
    assert setup['qr_png'].startswith('data:image/png;base64,')
    import time
    code = server.totp(setup['secret'], int(time.time()) // 30)
    confirm = c.post('/api/mfa/confirm', headers=h, json={'otp': code})
    assert confirm.status_code == 200 and len(confirm.json()['recovery_codes']) == 10
    # Les sessions sont fermées : reconnexion avec le code.
    assert c.get('/api/me', headers=h).status_code == 401
    code = server.totp(setup['secret'], int(time.time()) // 30 + 1)
    data, h = login(c, 'expl', otp=code)
    assert data['mfa_setup_required'] is False
    assert c.get('/api/units', headers=h).status_code == 200


def test_public_health_probe_reveals_nothing(env):
    r = env['c'].get('/healthz')
    assert r.status_code == 200 and r.json() == {'status': 'ok'}
