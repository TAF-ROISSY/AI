import os, tempfile, importlib
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient


def test_audit_warehouse_isolation_and_roles():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        def login(username,password):
            token=client.post('/api/login',json={'username':username,'password':password}).json()['token']
            return {'Authorization':'Bearer '+token}
        root=login('admin','TestPassword12345!')
        for username,warehouses in [('managerafr',['Afrique']),('managermar',['Maritime']),('workerafr',['Afrique'])]:
            role='worker' if username.startswith('worker') else 'manager'
            assert client.post('/api/users',headers=root,json={'username':username,'password':'Password12345!','role':role,'warehouses':warehouses}).status_code==200
        afr=login('managerafr','Password12345!')
        mar=login('managermar','Password12345!')
        worker=login('workerafr','Password12345!')
        ia=client.post('/api/incidents',headers=afr,json={'warehouse':'Afrique','category':'damage','severity':'major','description':'Incident Afrique'}).json()['id']
        im=client.post('/api/incidents',headers=mar,json={'warehouse':'Maritime','category':'damage','severity':'major','description':'Incident Maritime'}).json()['id']
        a=client.get('/api/audit',headers=afr)
        assert a.status_code==200,a.text
        refs={x['ref'] for x in a.json()}
        assert ia in refs and im not in refs
        assert client.get('/api/audit',headers=worker).status_code==403
        assert client.get('/api/audit',headers=root).status_code==200
        assert client.post('/api/drivers',headers=worker,json={'name':'  '}).status_code==400


def test_concurrent_release_reservations_never_exceed_stock():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        with TestClient(server.app) as client:
            token=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
            h={'Authorization':'Bearer '+token}
            customer=client.get('/api/clients',headers=h).json()[0]['id']
            receipt=client.post('/api/receipts',headers=h,json={'warehouse':'Afrique','client_id':customer,'expected':1,'actual':1,'weight':10}).json()['id']
            unit=client.post('/api/units',headers=h,json={'receipt_id':receipt,'description':'Test concurrence','quantity':1,'weight':10}).json()['id']
            def reserve(_):
                with TestClient(server.app) as c:
                    return c.post('/api/releases',headers=h,json={'unit_id':unit,'quantity':1}).status_code
            with ThreadPoolExecutor(max_workers=6) as pool:
                statuses=list(pool.map(reserve,range(6)))
            assert statuses.count(200)==1,statuses
            assert len(client.get('/api/releases',headers=h).json())==1
