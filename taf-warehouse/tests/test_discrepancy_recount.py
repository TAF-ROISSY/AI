import os,tempfile,importlib
from fastapi.testclient import TestClient

def test_independent_recount_and_receipt_discrepancy():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        c=TestClient(server.app)
        def login(name,password):
            r=c.post('/api/login',json={'username':name,'password':password})
            assert r.status_code==200,r.text
            return {'Authorization':'Bearer '+r.json()['token']}
        a=login('admin','TestPassword12345!')
        def post(h,url,data):return c.post('/api/'+url,headers=h,json=data)
        for name,role in [('worker1','worker'),('worker2','worker'),('manager1','manager')]:
            r=post(a,'users',{'username':name,'password':'LongPassword12345!','role':role,'warehouses':['Afrique']})
            assert r.status_code==200,r.text
        w1=login('worker1','LongPassword12345!')
        w2=login('worker2','LongPassword12345!')
        mgr=login('manager1','LongPassword12345!')
        cli=c.get('/api/clients',headers=a).json()[0]['id']
        rec=post(w1,'receipts',{'warehouse':'Afrique','client_id':cli,'awb':'TEST','expected':4,'actual':3,'weight':30}).json()['id']
        unit=post(w1,'units',{'receipt_id':rec,'description':'Palette','quantity':3,'weight':30,'volume':.1,'dimensions_ok':True}).json()['id']
        disc=post(w1,'receipts/'+rec+'/discrepancy',{'kind':'missing','description':'Un colis manquant'}).json()['id']
        assert post(w1,'receipt-discrepancies/'+disc+'/review',{'approve':True,'decision':'Réserves acceptées'}).status_code==403
        assert post(mgr,'receipt-discrepancies/'+disc+'/review',{'approve':True,'decision':'Réserves acceptées'}).status_code==200
        assert c.get('/api/units',headers=a).json()[0]['hold']
        assert post(w1,'releases',{'unit_id':unit,'quantity':1}).status_code==400
        assert post(mgr,'units/'+unit+'/hold',{'hold':'','reason':'Réserves traitées'}).status_code==200
        assert c.put('/api/locations/AFR-R01-A1',headers=mgr,json={'capacity_kg':1000,'capacity_m3':10,'verified':True,'notes':'Plaque constructeur vérifiée'}).status_code==200
        version=next(x for x in c.get('/api/units',headers=a).json() if x['id']==unit)['version']
        assert post(w1,'move',{'unit_id':unit,'destination':'AFR-R01-A1','expected_version':version}).status_code==200
        inv=post(w1,'counts',{'unit_id':unit,'observed':2,'reason':'Inventaire'}).json()['id']
        assert post(mgr,'counts/'+inv+'/review',{'approve':True,'reason':'Écart constaté'}).status_code==409
        assert post(w1,'counts/'+inv+'/recount',{'observed':2}).status_code==403
        assert post(w2,'counts/'+inv+'/recount',{'observed':2}).status_code==200
        assert post(w2,'counts/'+inv+'/review',{'approve':True,'reason':'Écart confirmé'}).status_code==403
        assert post(mgr,'counts/'+inv+'/review',{'approve':True,'reason':'Écart confirmé'}).status_code==200
        assert next(x for x in c.get('/api/units',headers=a).json() if x['id']==unit)['quantity']==2
