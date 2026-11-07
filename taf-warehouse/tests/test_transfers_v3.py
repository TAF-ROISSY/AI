import os,tempfile,importlib,base64,io
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient

def test_transfer_requires_separate_people_and_physical_dispatch():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        c=TestClient(server.app)
        def login(name,password):
            r=c.post('/api/login',json={'username':name,'password':password});assert r.status_code==200,r.text
            return {'Authorization':'Bearer '+r.json()['token']}
        admin=login('admin','TestPassword12345!')
        for name,role in [('manager_test','manager'),('worker_test','worker')]:
            r=c.post('/api/users',headers=admin,json={'username':name,'password':'TestPassword12345!','role':role,'warehouses':['Afrique','Maritime']})
            assert r.status_code==200,r.text
        manager=login('manager_test','TestPassword12345!');worker=login('worker_test','TestPassword12345!')
        client=c.get('/api/clients',headers=admin).json()[0]['id']
        rec=c.post('/api/receipts',headers=admin,json={'warehouse':'Afrique','client_id':client,'expected':1,'actual':1,'weight':100}).json()['id']
        unit=c.post('/api/units',headers=admin,json={'receipt_id':rec,'description':'Palette','quantity':1,'weight':100}).json()['id']
        from helpers import putaway; putaway(server, unit)  # Lot 3 : rangement avant sortie/transfert
        transfer=c.post('/api/transfers',headers=admin,json={'unit_id':unit,'destination':'Maritime'});assert transfer.status_code==200,transfer.text
        tid=transfer.json()['id']
        assert c.post('/api/transfers/'+tid+'/approve',headers=admin).status_code==403
        assert c.post('/api/transfers/'+tid+'/dispatch',headers=worker,json={'confirmation':True,'note':'Camion 12345'}).status_code==409
        assert c.post('/api/releases',headers=admin,json={'unit_id':unit,'quantity':1}).status_code==409
        assert c.post('/api/transfers/'+tid+'/approve',headers=manager).status_code==200
        driver=c.post('/api/drivers',headers=admin,json={'name':'Test Driver','company':'TAF','plate':'AA-123-AA'}).json()['id']
        buf=io.BytesIO();img=Image.new('RGB',(200,80),'white');draw=ImageDraw.Draw(img);[draw.line((i,10,i+40,50),fill=(i%255,20,80),width=2) for i in range(0,160,5)];img.save(buf,format='PNG')
        signed={'driver_id':driver,'signature_name':'Test Driver','signature_data':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'signature_consent':True}
        assert c.post('/api/transfers/'+tid+'/dispatch',headers=worker,json={'confirmation':False,'note':'Camion 12345',**signed}).status_code==400
        assert c.post('/api/transfers/'+tid+'/dispatch',headers=worker,json={'confirmation':True,'note':'Camion 12345',**signed}).status_code==200
        pdf=c.get('/api/transfers/'+tid+'/dispatch-pdf',headers=worker)
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
        assert c.post('/api/transfers/'+tid+'/receive',headers=worker).status_code==403
        assert c.post('/api/transfers/'+tid+'/receive',headers=manager).status_code==200
        assert c.post('/api/transfers/'+tid+'/receive',headers=admin).status_code==409
        row=next(x for x in c.get('/api/units',headers=admin).json() if x['id']==unit)
        assert row['warehouse']=='Maritime' and row['status']=='awaiting_putaway'
        assert len(c.get('/api/locations',headers=admin).json())==4*49
