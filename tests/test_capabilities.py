import json
from test_ai_workflows import provider
from backend import store,worker
from backend.capabilities import verified
from backend.providers import configured

def test_explicit_probe_in_worker_and_configuration_signature(provider):
    client,state,_=provider
    assert not verified(configured('translation'),'text')
    assert client.post('/api/providers/translation/probe',json={'capability':'text'}).status_code==422
    assert client.post('/api/providers/translation/probe',json={'capability':'text','confirmed':True}).status_code==202
    assert client.post('/api/providers/translation/probe',json={'capability':'text','confirmed':True}).status_code==409
    assert worker.run_once()
    response=client.get('/api/providers/translation/capabilities').json()
    assert response['capabilities']['text']['verified'] and not response['video_native']
    assert 'config' not in response and 'owner' not in response
    config=configured('translation');config['model']='another-model'
    client.put('/api/settings',json={'providers':[config]})
    assert not verified(configured('translation'),'text')

def test_schema_upgrade_preserves_project(provider):
    client,state,_=provider;p=client.post('/api/projects',json={'name':'Kept project'}).json()
    with store.connect() as db:
        db.execute('DROP TABLE pipelines');db.execute('DROP TABLE provider_checks');db.execute('PRAGMA user_version=3')
    store.migrate()
    assert client.get('/api/projects/'+p['id']).json()['name']=='Kept project'
    with store.connect() as db:assert db.execute('PRAGMA user_version').fetchone()[0]==4
