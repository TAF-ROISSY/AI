import os, tempfile, importlib
from fastapi.testclient import TestClient

def test_four_modules():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['TAF_DATA_DIR']=tmp
        os.environ['TAF_ADMIN_PASSWORD']='TestPassword12345!'
        from app import server
        importlib.reload(server)
        client=TestClient(server.app)
        token=client.post('/api/login',json={'username':'admin','password':'TestPassword12345!'}).json()['token']
        h={'Authorization':'Bearer '+token}
        def post(url,data={}):return client.post('/api/'+url,json=data,headers=h)
        def get(url):return client.get('/api/'+url,headers=h)
        def put(url,data):return client.put('/api/'+url,json=data,headers=h)
        mission=post('missions',{'warehouse':'Afrique','title':'Inventaire mensuel'});assert mission.status_code==200,mission.text
        mid=mission.json()['id']
        assert post('missions/'+mid+'/plan',{'priority':'urgent','description':'Zone Afrique'}).status_code==200
        task=post('missions/'+mid+'/tasks',{'title':'Contrôler rack'});assert task.status_code==200,task.text
        tid=task.json()['id']
        assert post('tasks/'+tid+'/plan',{'priority':'high','assignee':'admin','notes':'Contrôle visuel'}).status_code==200
        assert post('tasks/'+tid+'/start',{'note':'Début contrôle'}).status_code==200
        assert post('tasks/'+tid+'/done').status_code==200
        assert post('missions/'+mid+'/close').status_code==200
        assert len(get('task-events').json())==1
        loc='AFR-R01-A1'
        assert put('locations/'+loc,{'capacity_kg':1000,'capacity_m3':5,'verified':True,'notes':'Plaque constructeur validée'}).status_code==200
        rule={'max_unit_kg':500,'max_unit_m3':2,'max_units':3,'allowed_categories':['general'],'forbidden_categories':['hazmat'],'technical_reference':'plaque constructeur n123'}
        assert put('rack-rules/'+loc,rule).status_code==200
        assert len(get('rack-rules').json())==1
        claim=post('claims',{'warehouse':'Afrique','description':'Palette abîmée'});assert claim.status_code==200,claim.text
        cid=claim.json()['id']
        assert post('claims/'+cid+'/action',{'action':'close','note':'Clôture refusée'}).status_code==400
        assert post('claims/'+cid+'/action',{'action':'decision','note':'Réclamation retenue'}).status_code==200
        assert len(get('claim-actions').json())==1
        user=post('users',{'username':'worker35','password':'TestPassword12345!','role':'worker','warehouses':['Afrique']});assert user.status_code==200,user.text
        userid=next(x['id'] for x in get('users').json() if x['username']=='worker35')
        assert post('users/'+userid+'/status',{'active':False}).status_code==200
        assert client.post('/api/login',json={'username':'worker35','password':'TestPassword12345!'}).status_code==401
        assert post('users/'+userid+'/reset-password',{'password':'AnotherPassword12345!'}).status_code==200
