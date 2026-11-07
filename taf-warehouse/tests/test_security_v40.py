import os,tempfile,importlib,time
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

def test_encrypted_mfa_and_one_time_recovery():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        os.environ['TAF_MFA_ENCRYPTION_KEY']=Fernet.generate_key().decode()
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        credentials={'username':'admin','password':'TestPassword12345!'}
        token=client.post('/api/login',json=credentials).json()['token']
        headers={'Authorization':'Bearer '+token}
        setup=client.post('/api/mfa/setup',headers=headers)
        assert setup.status_code==200
        secret=setup.json()['secret']
        with server.db() as db:
            record=server.one(db,'SELECT secret FROM mfa')
        assert record['secret'].startswith('enc:v1:') and secret not in record['secret']
        confirm=client.post('/api/mfa/confirm',headers=headers,json={'otp':server.totp(secret,int(time.time())//30)})
        assert confirm.status_code==200
        codes=confirm.json()['recovery_codes']
        assert len(codes)==10
        recovered=client.post('/api/login',json={**credentials,'recovery_code':codes[0]})
        assert recovered.status_code==200,recovered.text
        assert client.post('/api/login',json={**credentials,'recovery_code':codes[0]}).status_code==401
        assert client.post('/api/login',json={**credentials,'recovery_code':codes[1]}).status_code==200
