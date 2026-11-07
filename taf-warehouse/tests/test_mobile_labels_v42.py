import importlib, tempfile
from fastapi.testclient import TestClient

def test_batch_thermal_labels(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv('TAF_DATA_DIR',tmp)
        monkeypatch.setenv('TAF_ADMIN_PASSWORD','TestPassword12345!')
        from app import server
        importlib.reload(server)
        c=TestClient(server.app)
        assert c.get('/api/labels-batch?ids=ABC').status_code==401
        token=c.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
        h={'Authorization':'Bearer '+token}
        client=c.get('/api/clients',headers=h).json()[0]['id']
        r=c.post('/api/receipts',headers=h,json={'warehouse':'Afrique','client_id':client,'awb':'057-12345675','expected':2,'actual':2,'weight':30})
        assert r.status_code==200,r.text
        receipt=r.json()['id']
        ids=[]
        for i in range(2):
            x=c.post('/api/units',headers=h,json={'receipt_id':receipt,'description':f'Carton {i}','quantity':1,'weight':15,'volume':.1,'dimensions_ok':True})
            assert x.status_code==200,x.text
            ids.append(x.json()['id'])
        response=c.get('/api/labels-batch',params={'ids':','.join(ids)},headers=h)
        assert response.status_code==200 and response.content.startswith(b'%PDF')
        from pypdf import PdfReader
        import io
        assert len(PdfReader(io.BytesIO(response.content)).pages)==2
        assert c.get('/api/labels-batch',params={'ids':','.join(ids*2)},headers=h).status_code==400
        assert c.get('/api/labels-batch',params={'ids':'FAKE'},headers=h).status_code in (400,404)
