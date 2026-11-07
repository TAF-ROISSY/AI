import os, tempfile, importlib
from fastapi.testclient import TestClient

def test_persistent_account_lockout_and_password_policy():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        for _ in range(5):
            assert client.post('/api/login',json={'username':'admin','password':'incorrect'}).status_code==401
        assert client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).status_code==429
        importlib.reload(server)
        client=TestClient(server.app)
        assert client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).status_code==429
        with server.db() as c:
            c.execute('UPDATE login_security SET locked_until=0,failures=0 WHERE username=?',('admin',))
        login=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'})
        assert login.status_code==200
        h={'Authorization':'Bearer '+login.json()['token']}
        weak=client.post('/api/password',headers=h,json={'old':'TestPassword12345!','new':'aaaaaaaaaaaa'})
        assert weak.status_code==400
        assert client.get('/api/me',headers=h).status_code==200
        assert client.get('/api/me',headers=h).headers['x-frame-options']=='DENY'
        changed=client.post('/api/password',headers=h,json={'old':'TestPassword12345!','new':'AnotherSecurePassword567!'})
        assert changed.status_code==200,changed.text
        assert client.get('/api/me',headers=h).status_code==401

def test_production_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_ENV']='production'
        try:
            from app import server
            importlib.reload(server)
            assert False,'Production should not boot'
        except RuntimeError as exc:
            assert 'Démarrage en production refusé' in str(exc)  # lot 6 : refus tant que la configuration est incomplète
        finally:
            os.environ.pop('TAF_ENV',None)
            importlib.reload(server)
