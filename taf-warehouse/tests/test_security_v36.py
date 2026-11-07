import os, tempfile, importlib
from fastapi.testclient import TestClient

def test_security_and_session_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        assert client.get('/api/health').status_code==401
        for _ in range(5):
            assert client.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==401
        assert client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).status_code==429
        server._login_attempts.clear()
        with server.db() as c:
            c.execute('UPDATE login_security SET locked_until=0,failures=0 WHERE username=?',('admin',))
        login=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'})
        assert login.status_code==200
        headers={'Authorization':'Bearer '+login.json()['token']}
        health=client.get('/api/health',headers=headers)
        assert health.status_code==200 and health.json()['database']=='ok'
        assert health.headers['x-content-type-options']=='nosniff'
        assert health.headers['cache-control']=='no-store'
        assert client.post('/api/logout',headers=headers).status_code==200
        assert client.get('/api/me',headers=headers).status_code==401
