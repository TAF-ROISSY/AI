import os, tempfile, importlib
from fastapi.testclient import TestClient

def test_cancel_reservations_and_transfer_independence():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        token=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
        h={'Authorization':'Bearer '+token}
        post=lambda url,payload={}:client.post('/api/'+url,headers=h,json=payload)
        get=lambda url:client.get('/api/'+url,headers=h)
        cli=get('clients').json()[0]['id']
        rec=post('receipts',{'warehouse':'Afrique','client_id':cli,'expected':2,'actual':2,'weight':40}).json()['id']
        unit=post('units',{'receipt_id':rec,'description':'Palette','quantity':2,'weight':40,'dimensions_ok':True}).json()['id']
        out=post('releases',{'unit_id':unit,'quantity':2}).json()['id']
        assert post('transfers',{'unit_id':unit,'destination':'Maritime'}).status_code==409
        assert post('releases/'+out+'/cancel').status_code==200
        assert post('releases/'+out+'/cancel').status_code==409
        transfer=post('transfers',{'unit_id':unit,'destination':'Maritime'}).json()['id']
        assert post('transfers/'+transfer+'/approve').status_code==403
        assert post('transfers/'+transfer+'/cancel').status_code==200
        assert post('transfers/'+transfer+'/dispatch',{'confirmation':True,'note':'Véhicule test'}).status_code==409
        assert post('releases',{'unit_id':unit,'quantity':2}).status_code==200
