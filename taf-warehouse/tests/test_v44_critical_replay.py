import importlib, os, tempfile
from fastapi.testclient import TestClient

def test_inventory_review_idempotent_and_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        c=TestClient(server.app)
        token=c.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
        h={'Authorization':'Bearer '+token}
        client=c.get('/api/clients',headers=h).json()[0]['id']
        resp=c.post('/api/receipts',headers=h,json={'warehouse':'Afrique','client_id':client,'expected':1,'actual':1,'weight':1});assert resp.status_code==200,resp.text
        receipt=resp.json()['id']
        unit=c.post('/api/units',headers=h,json={'receipt_id':receipt,'description':'Test','quantity':1,'weight':1}).json()['id']
        with server.db() as db:
            db.execute("UPDATE units SET location_id=?,status='available' WHERE id=?",('AFR-TEMP',unit))
        count=c.post('/api/counts',headers=h,json={'unit_id':unit,'observed':1}).json()['id']
        # Independent reviewer required, even with an idempotency key.
        key={**h,'Idempotency-Key':'test-review-unique-001'}
        denied=c.post(f'/api/counts/{count}/review',headers=key,json={'approve':True,'reason':'ok'})
        assert denied.status_code==403
        # No idempotency result is stored for a denied request.
        with server.db() as db:
            assert db.execute('SELECT COUNT(*) FROM idempotency WHERE operation="inventory.review"').fetchone()[0]==0
