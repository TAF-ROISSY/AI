import os, tempfile, importlib
from fastapi.testclient import TestClient

def test_move_and_count_replay():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        with TestClient(server.app) as c:
            login=c.post('/api/login',json={'username':'admin','password':'TestPassword12345!'})
            assert login.status_code==200
            h={'Authorization':'Bearer '+login.json()['token']}
            def post(path,data,key=None):
                return c.post('/api/'+path,json=data,headers={**h,**({'Idempotency-Key':key} if key else {})})
            def get(path):return c.get('/api/'+path,headers=h).json()
            client=get('clients')[0]['id']
            receipt=post('receipts',{'warehouse':'Afrique','client_id':client,'expected':1,'actual':1,'weight':10}).json()['id']
            unit=post('units',{'receipt_id':receipt,'description':'Test','quantity':1,'weight':10,'volume':0.1,'dimensions_ok':True}).json()['id']
            dest=next(l['id'] for l in get('locations') if l['warehouse']=='Afrique')
            with server.db() as db:
                db.execute('UPDATE locations SET verified=1,capacity_kg=1000,capacity_m3=10 WHERE id=?',(dest,))
            body={'unit_id':unit,'destination':dest,'expected_version':0,'reason':'Test de rangement'}
            a=post('move',body,'move-replay-12345');b=post('move',body,'move-replay-12345')
            assert a.status_code==200,a.text
            assert a.json()==b.json()
            assert post('move',{**body,'reason':'Different'},'move-replay-12345').status_code==409
            cb={'unit_id':unit,'observed':1,'reason':'Inventaire test'}
            a=post('counts',cb,'count-replay-12345');b=post('counts',cb,'count-replay-12345')
            assert a.status_code==200,a.text
            assert a.json()==b.json()
            assert post('counts',{**cb,'observed':0},'count-replay-12345').status_code==409
            assert len([x for x in get('counts') if x['unit_id']==unit])==1
