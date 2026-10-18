"""Controlled adapters prove orchestration, never live AI quality."""
import json
from test_ai_workflows import provider,source
from backend import store,worker
from backend.providers import configured
from backend.capabilities import record


def launch(client,p,**options):
    body={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'targets':['vi'],'output':'subtitles',**options}
    plan=client.post(f'/api/projects/{p["id"]}/auto/plan',json=body)
    assert plan.status_code==200,plan.text
    assert not plan.json()['blockers'],plan.text
    result=client.post(f'/api/projects/{p["id"]}/auto',json={**body,'confirmed':True,'consent_signature':plan.json()['signature']})
    assert result.status_code==202,result.text
    return result.json()['id']


def finish(client,pid):
    for _ in range(12):
        worker.run_once()
        p=client.get(f'/api/projects/{pid}/auto').json()[0]
        if p['state']!='running':return p
    raise AssertionError('Pipeline did not finish')


def test_auto_priority_multilingual_exports(provider):
    client,state,_=provider;p=source(client)
    # Discovery alone must not permit inference or send data.
    client.post('/api/providers/translation/check')
    plan=client.post(f'/api/projects/{p["id"]}/auto/plan',json={'revision':p['revision'],'track_id':p['tracks'][0]['id']}).json()
    assert plan['blockers'] and not state['requests']
    record(configured('translation'),'text','fixture_validation')
    launch(client,p,targets=['vi','en'],context_note='Use consistent office relationships.')
    result=finish(client,p['id']);assert result['state']=='succeeded',result
    assert len(result['outputs'])==6
    assert not any(r.get('asr') for r in state['requests'])
    assert all(r.get('context_note')=='Use consistent office relationships.' for r in state['requests'] if 'cues' in r)
    for f in result['outputs']:
        response=client.get(f'/api/projects/{p["id"]}/auto-exports/{f["job_id"]}/{f["track_id"]}/{f["format"]}')
        assert response.status_code==200 and 'fixture-' in response.text
    latest=client.get(f'/api/projects/{p["id"]}').json()
    assert latest['tracks'][0]==p['tracks'][0]


def test_auto_cancel_retry_source_invalidation(provider):
    client,state,_=provider;p=source(client);pid=p['id'];record(configured('translation'),'text','fixture_validation')
    id=launch(client,p)
    client.post(f'/api/projects/{pid}/auto/{id}/cancel')
    worker.run_once();assert not state['requests']
    client.post(f'/api/projects/{pid}/auto/{id}/retry')
    # Schedule but do not run the child; editing source must cancel that child.
    from backend.pipelines import tick
    tick()
    p=client.get(f'/api/projects/{pid}').json();cues=p['tracks'][0]['cues'];cues[0]['text']='Changed'
    client.put(f'/api/projects/{pid}/tracks/{p["tracks"][0]["id"]}',json={'revision':p['revision'],'cues':cues})
    worker.run_once();result=client.get(f'/api/projects/{pid}/auto').json()[0]
    assert result['state']=='failed' and not state['requests']
    with store.connect() as db:assert db.execute('SELECT state FROM jobs').fetchone()[0]=='canceled'


def test_auto_consent_config_changed_and_ai_track_guard(provider):
    client,state,_=provider;p=source(client);pid=p['id'];record(configured('translation'),'text','fixture_validation')
    body={'revision':p['revision'],'track_id':p['tracks'][0]['id']}
    plan=client.post(f'/api/projects/{pid}/auto/plan',json=body).json()
    assert client.post(f'/api/projects/{pid}/auto',json={**body,'confirmed':True,'consent_signature':'wrong'}).status_code==409
    provider=configured('translation');provider['model']='different-model'
    client.put('/api/settings',json={'providers':[provider]})
    assert client.post(f'/api/projects/{pid}/auto',json={**body,'confirmed':True,'consent_signature':plan['signature']}).status_code==422
    with store.connect() as db:
        doc=store.project(db,pid);doc['tracks'][0]['kind']='description';store.save(db,doc)
    body['revision']+=1
    assert client.post(f'/api/projects/{pid}/auto/plan',json=body).status_code==422


def test_auto_same_language_and_not_yet_available_modes(provider):
    client,state,_=provider;p=source(client);record(configured('translation'),'text','fixture_validation')
    with store.connect() as db:
        p=store.project(db,p['id']);p['tracks'][0]['language']='vi';store.save(db,p)
    launch(client,p,targets=[p['tracks'][0]['language']])
    result=finish(client,p['id']);assert result['state']=='succeeded' and len(result['outputs'])==3,result
    assert not state['requests']
    p=client.get(f'/api/projects/{p["id"]}').json()
    plan=client.post(f'/api/projects/{p["id"]}/auto/plan',json={'revision':p['revision'],'mode':'review','output':'subtitles','track_id':p['tracks'][0]['id']}).json()
    assert plan['blockers']

def test_one_active_pipeline_per_project(provider):
    client,state,_=provider;p=source(client);record(configured('translation'),'text','fixture_validation')
    launch(client,p)
    body={'revision':p['revision'],'track_id':p['tracks'][0]['id']}
    plan=client.post(f'/api/projects/{p["id"]}/auto/plan',json=body).json()
    r=client.post(f'/api/projects/{p["id"]}/auto',json={**body,'confirmed':True,'consent_signature':plan['signature']})
    assert r.status_code==409 and not state['requests']
