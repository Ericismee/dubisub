import subprocess
import pytest
from test_ai_workflows import provider,source
from test_pipelines import launch,finish
from backend import worker
from backend.capabilities import record
from backend.providers import configured,ProviderError
from backend.analysis import validate_items

def test_unknown_evidence_rejected():
    with pytest.raises(ProviderError):validate_items({'items':[{'text':'Invented','evidence_ids':['fake']}]},{})

def test_transcript_summary_seek_ranges_edit_and_export(provider):
    client,state,_=provider;p=source(client);record(configured('translation'),'text','fixture_validation')
    launch(client,p,mode='summary',output='draft')
    result=finish(client,p['id']);assert result['state']=='draft',result
    p=client.get('/api/projects/'+p['id']).json();artifact=next(iter(p['analyses'].values()))
    assert artifact['scope']=='transcript_only' and artifact['items'][0]['source_ranges'][0]['start_ms']==100
    artifact['items'][0]['text']='User edited'
    assert client.put(f'/api/projects/{p["id"]}/analyses/{artifact["id"]}',json={'revision':p['revision'],'items':artifact['items'],'reviewed':True}).status_code==200
    md=client.get(f'/api/projects/{p["id"]}/analyses/{artifact["id"]}/export');assert 'User edited' in md.text and 'transcript_only' in md.text
    artifact['items'][0]['evidence_ids']=['invented']
    response=client.put(f'/api/projects/{p["id"]}/analyses/{artifact["id"]}',json={'revision':p['revision']+1,'items':artifact['items']})
    assert response.status_code in (409,422)

def test_sampled_video_no_audio_description(provider):
    client,state,directory=provider
    video=directory/'silent.mp4';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:duration=1','-c:v','libx264','-y',str(video)],check=True)
    pid=client.post('/api/projects',json={'name':'Silent video'}).json()['id']
    with video.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('silent.mp4',f)})
    worker.run_once();p=client.get('/api/projects/'+pid).json()
    config=configured('translation');record(config,'text','fixture_validation')
    client.put('/api/settings',json={'providers':[config,{**config,'kind':'vision'}]})
    body={'revision':p['revision'],'asset_id':p['assets'][0]['id'],'mode':'describe','use_vision':True,'output':'draft'}
    assert client.post(f'/api/projects/{pid}/auto/plan',json=body).json()['blockers']
    record(config,'image','fixture_validation')
    plan=client.post(f'/api/projects/{pid}/auto/plan',json=body).json();assert not plan['blockers'],plan
    assert client.post(f'/api/projects/{pid}/auto',json={**body,'confirmed':True,'consent_signature':plan['signature']}).status_code==202
    result=finish(client,pid);assert result['state']=='draft',result
    p=client.get('/api/projects/'+pid).json();assert not p['tracks']
    scenes=next(v for v in p['analyses'].values() if v['kind']=='scenes')
    assert scenes['sampled_timestamps_ms']==[500] and scenes['items'][0]['source_ranges'][0]['type']=='image'
    assert any(r.get('vision') for r in state['requests']) and not any(r.get('asr') for r in state['requests'])
