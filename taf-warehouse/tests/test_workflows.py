import os,tempfile,importlib,base64,io
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient

def test_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        login=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'})
        assert login.status_code==200,login.text
        headers={'Authorization':'Bearer '+login.json()['token']}
        get=lambda path:client.get('/api/'+path,headers=headers)
        post=lambda path,body:client.post('/api/'+path,headers=headers,json=body)
        clients=get('clients').json()
        r=post('receipts',{'warehouse':'Afrique','client_id':clients[0]['id'],'awb':'057-12345675','expected':2,'actual':2,'weight':400})
        assert r.status_code==200,r.text
        receipt=r.json()['id']
        unit=post('units',{'receipt_id':receipt,'description':'Palette test','quantity':2,'weight':400,'volume':1.2,'dimensions_ok':True}).json()['id']
        unitrow=next(x for x in get('units').json() if x['id']==unit)
        loc=next(x for x in get('locations').json() if x['id']=='AFR-R01-A1')
        # Cannot move into unverified racks.
        assert post('move',{'unit_id':unit,'destination':loc['id'],'expected_version':unitrow['version']}).status_code==400
        config=client.put('/api/locations/'+loc['id'],headers=headers,json={'capacity_kg':1000,'capacity_m3':3,'verified':True,'notes':'Plaque constructeur vérifiée en TEST'})
        assert config.status_code==200,config.text
        assert post('move',{'unit_id':unit,'destination':loc['id'],'expected_version':unitrow['version']}).status_code==200
        assert post('move',{'unit_id':unit,'destination':loc['id'],'expected_version':unitrow['version']}).status_code==409
        out=post('releases',{'unit_id':unit,'quantity':1}).json()['id']
        assert post('releases/'+out+'/complete',{'driver_id':'none','signature_name':'test','signature_data':'test'}).status_code==422
        assert post('releases/'+out+'/authorize',{}).status_code==200
        driver=post('drivers',{'name':'Chauffeur test'}).json()['id']
        img=Image.new('RGB',(400,140),'white');draw=ImageDraw.Draw(img);draw.line([(15,90),(70,45),(150,100),(260,30),(380,85)],fill='black',width=5)
        bio=io.BytesIO();img.save(bio,format='PNG');signature='data:image/png;base64,'+base64.b64encode(bio.getvalue()).decode()
        assert post('releases/'+out+'/complete',{'driver_id':driver,'signature_name':'Test','signature_data':'signature test','signature_consent':True}).status_code==422
        assert post('releases/'+out+'/complete',{'driver_id':driver,'signature_name':'Test','signature_data':signature,'signature_consent':True}).status_code==200
        pdf=get('releases/'+out+'/handover-pdf');assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
        assert next(x for x in get('units').json() if x['id']==unit)['quantity']==1
        incident=post('incidents',{'warehouse':'Afrique','unit_id':unit,'category':'damage','severity':'major','description':'Carton abîmé'}).json()['id']
        assert next(x for x in get('units').json() if x['id']==unit)['hold']
        assert post('releases',{'unit_id':unit,'quantity':1}).status_code==400
        claim=post('claims',{'warehouse':'Afrique','incident_id':incident,'description':'Réclamation test'}).json()['id']
        assert get('reports/claim/'+claim).status_code==200
        assert get('labels/'+unit).status_code==200

def test_notifications_and_permissions():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        token=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
        h={'Authorization':'Bearer '+token}
        r=client.post('/api/incidents',headers=h,json={'warehouse':'Afrique','category':'damage','severity':'critical','description':'Rack instable'})
        assert r.status_code==200,r.text
        notes=client.get('/api/notifications',headers=h).json()
        assert len(notes)==1 and notes[0]['is_read']==0
        nid=notes[0]['id']
        assert client.post('/api/notifications/'+nid+'/read',headers=h).status_code==200
        assert client.get('/api/notifications',headers=h).json()[0]['is_read']==1
        assert client.get('/api/notifications').status_code==401
