import hashlib
import json
import subprocess
import pytest
from test_ai_workflows import provider,source
from test_pipelines import launch,finish
from backend import store,worker
from backend.capabilities import record
from backend.providers import configured
from backend.rendering import normalize_plan

def video(client,directory,pid):
    path=directory/'owned.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:duration=2','-f','lavfi','-i','sine=duration=2','-c:v','libx264','-c:a','aac','-shortest','-y',str(path)],check=True)
    with path.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('owned.mp4',f)})
    worker.run_once();p=client.get('/api/projects/'+pid).json()
    return path,next(a['id'] for a in p['assets'] if a['kind']=='media')

def test_blur_region_and_toggle_preserves_source(provider):
    import numpy as np
    client,state,directory=provider;p=source(client);pid=p['id'];path,aid=video(client,directory,pid);before=hashlib.sha256(path.read_bytes()).hexdigest();frames=[]
    for enabled in (False,True):
        p=client.get('/api/projects/'+pid).json()
        mask={'enabled':enabled,'x':.05,'y':.74,'width':.9,'height':.24,'strength':8}
        r=client.post(f'/api/projects/{pid}/render',json={'revision':p['revision'],'asset_id':aid,'burn_subtitles':False,'plan':{'resolution':360,'subtitle_mask':mask}})
        assert r.status_code==202,r.text
        worker.run_once();p=client.get('/api/projects/'+pid).json();assert p['jobs'][-1]['state']=='succeeded',p['jobs'][-1]
        item=p['artifacts'][-1];file=store.root()/'artifacts'/f'{item["id"]}.mp4'
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss','0.5','-i',str(file),'-frames:v','1','-pix_fmt','gray','-f','rawvideo','pipe:1'])
        frames.append(np.frombuffer(raw,dtype=np.uint8).reshape(360,640).astype(float))
    diff=abs(frames[0]-frames[1]);assert diff[270:340,40:600].mean()>5
    assert diff[20:220,40:600].mean()<3
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    with pytest.raises(ValueError):normalize_plan({'subtitle_mask':{'enabled':True,'x':.8,'width':.5}},2000)

def test_auto_asr_translate_overlay_mp4_keeps_old_track(provider):
    client,state,directory=provider;p=source(client);pid=p['id'];original=p['tracks'][0];path,aid=video(client,directory,pid)
    record(configured('translation'),'text','fixture_validation');p=client.get('/api/projects/'+pid).json()
    launch(client,p,asset_id=aid,force_asr=True,output='video',render_plan={'resolution':360,'subtitle_mask':{'enabled':True}})
    result=finish(client,pid);assert result['state']=='succeeded',result
    assert len(result['outputs'])==3 and len(result['videos'])==1
    p=client.get('/api/projects/'+pid).json();assert p['tracks'][0]==original
    assert [t['kind'] for t in p['tracks'][1:]]==['asr','translation']
    assert p['tracks'][-1]['language']=='vi'

def test_restart_exhausted_job_uses_current_provider_and_keeps_history(provider):
    client,state,directory=provider;p=source(client);pid=p['id'];_,aid=video(client,directory,pid)
    response=client.post(f'/api/projects/{pid}/transcribe',json={'asset_id':aid,'source_language':'en'});jid=response.json()['job_id']
    with store.connect() as db:db.execute("UPDATE jobs SET state='failed',attempts=3,checkpoint='{}' WHERE id=?",(jid,))
    p=client.get('/api/projects/'+pid).json();assert not p['jobs'][-1]['can_retry']
    assert client.post(f'/api/jobs/{jid}/retry').status_code==409
    plan=client.get('/api/job-restarts/'+jid).json()
    assert client.post('/api/job-restarts/'+jid,json={'confirmed':False,'signature':plan['signature']}).status_code==409
    r=client.post('/api/job-restarts/'+jid,json={'confirmed':True,'signature':plan['signature']});assert r.status_code==202,r.text
    new=r.json()['job_id'];assert new!=jid
    assert client.post(f'/api/jobs/{new}/retry').status_code==200 # double click is idempotent
    worker.run_once()
    with store.connect() as db:
        assert db.execute('SELECT attempts FROM jobs WHERE id=?',(jid,)).fetchone()[0]==3
        assert db.execute('SELECT state FROM jobs WHERE id=?',(new,)).fetchone()[0]=='succeeded'

def test_retry_does_not_reuse_old_provider_after_settings_change(provider):
    client,state,directory=provider;p=source(client);pid=p['id'];_,aid=video(client,directory,pid)
    jid=client.post(f'/api/projects/{pid}/transcribe',json={'asset_id':aid}).json()['job_id']
    with store.connect() as db:db.execute("UPDATE jobs SET state='failed',attempts=1 WHERE id=?",(jid,))
    settings=client.get('/api/settings').json()['providers']
    for config in settings:
        if config['kind']=='asr':config['model']='new-model'
    client.put('/api/settings',json={'providers':settings})
    p=client.get('/api/projects/'+pid).json();job=next(j for j in p['jobs'] if j['id']==jid)
    assert not job['can_retry'] and job['retry_reason']=='provider_changed'
    assert client.post(f'/api/jobs/{jid}/retry').status_code==409
    assert client.get('/api/job-restarts/'+jid).json()['model']=='new-model'

def test_local_asr_rejects_changed_model_revision(tmp_path,monkeypatch):
    from backend.local_asr import transcribe,DEFAULT
    from backend.providers import ProviderError
    monkeypatch.setenv('DUBISUB_ASR_MODEL_DIR',str(tmp_path))
    model=tmp_path/'small';model.mkdir()
    for f in ('model.bin','config.json','tokenizer.json'):(model/f).write_text('fixture')
    (model/'source.json').write_text(json.dumps({'revision':'new'}))
    with pytest.raises(ProviderError,match='revision'):transcribe(tmp_path/'unused.wav',{**DEFAULT,'model_revision':'old'},'auto',lambda:None)
