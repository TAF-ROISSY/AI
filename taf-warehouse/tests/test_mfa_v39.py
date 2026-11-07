import os,tempfile,importlib,time
from fastapi.testclient import TestClient

def test_totp_activation_and_replay_protection():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        c=TestClient(server.app)
        creds={'username':'admin','password':'TestPassword12345!'}
        token=c.post('/api/login',json=creds).json()['token']
        h={'Authorization':'Bearer '+token}
        setup=c.post('/api/mfa/setup',headers=h)
        assert setup.status_code==200,setup.text
        secret=setup.json()['secret']
        code=server.totp(secret,int(time.time())//30)
        assert c.post('/api/mfa/confirm',headers=h,json={'otp':code}).status_code==200
        assert c.get('/api/me',headers=h).status_code==401
        assert c.post('/api/login',json=creds).status_code==401
        assert c.post('/api/login',json={**creds,'otp':code}).status_code==401
        nextcode=server.totp(secret,int(time.time())//30+1)
        success=c.post('/api/login',json={**creds,'otp':nextcode})
        assert success.status_code==200,success.text
        assert c.post('/api/login',json={**creds,'otp':nextcode}).status_code==401
