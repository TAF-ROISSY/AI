import os,tempfile,importlib,concurrent.futures
from fastapi.testclient import TestClient

def test_idempotency_and_movement_reservation():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        with TestClient(server.app) as client:
            token=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
            h={'Authorization':'Bearer '+token}
            post=lambda path,body={},extra={}:client.post('/api/'+path,headers={**h,**extra},json=body)
            get=lambda path:client.get('/api/'+path,headers=h)
            cli=get('clients').json()[0]['id']
            rec=post('receipts',{'warehouse':'Afrique','client_id':cli,'expected':3,'actual':3,'weight':30}).json()['id']
            unit=post('units',{'receipt_id':rec,'description':'Palette','quantity':3,'weight':30,'dimensions_ok':True}).json()['id']
            from helpers import putaway; putaway(server, unit)  # Lot 3 : rangement avant sortie/transfert
            key={'Idempotency-Key':'release-unique-00001'}
            body={'unit_id':unit,'quantity':2}
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                results=list(pool.map(lambda _:post('releases',body,key),range(5)))
            assert all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results]
            assert len({r.json()['id'] for r in results})==1
            assert post('releases',{'unit_id':unit,'quantity':1},key).status_code==409
            assert len([r for r in get('releases').json() if r['unit_id']==unit])==1
            assert post('move',{'unit_id':unit,'destination':'nonexistent','expected_version':0}).status_code in (400,404)
            assert post('releases/'+results[0].json()['id']+'/cancel').status_code==200
            tkey={'Idempotency-Key':'transfer-unique-00001'}
            transfer_body={'unit_id':unit,'destination':'Maritime'}
            t1=post('transfers',transfer_body,tkey)
            t2=post('transfers',transfer_body,tkey)
            assert t1.status_code==200 and t1.json()==t2.json()
            assert post('transfers',{'unit_id':unit,'destination':'TMS'},tkey).status_code==409
