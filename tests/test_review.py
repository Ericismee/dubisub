"""Real FFmpeg output timing with synthetic provider audio; no AI quality claim."""
import json
import subprocess
import hashlib
from test_ai_workflows import provider
from backend import store,worker,dubbing
from backend.providers import configured

def test_review_measured_output_timeline_cache_and_video(provider,monkeypatch):
    client,state,directory=provider
    monkeypatch.setattr(dubbing,'capability',lambda p:{'cloning':True})
    media=directory/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:duration=8','-c:v','libx264','-y',str(media)],check=True)
    checksum=hashlib.sha256(media.read_bytes()).hexdigest()
    pid=client.post('/api/projects',json={'name':'Review fixture'}).json()['id']
    with media.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('source.mp4',f)})
    worker.run_once();p=client.get('/api/projects/'+pid).json();aid=p['assets'][0]['id']
    script={'id':'script','kind':'review','language':'vi','reviewed':True,'items':[{'id':str(i),'text':'Fixture narration '+str(i),'source_ranges':[{'start_ms':5000+i*1000,'end_ms':6000+i*1000,'type':'image'}]} for i in range(2)]}
    with store.connect() as db:
        doc=store.project(db,pid);doc['analyses']={'script':script};store.save(db,doc);revision=doc['revision']
    body={'revision':revision,'analysis_id':'script','voice':{'kind':'preset','id':'fixture-vi'},'transfer_confirmed':True,'provider_fingerprint':dubbing.fingerprint(configured('tts')),'asset_id':aid,'export_video':True}
    r=client.post(f'/api/projects/{pid}/narrations',json=body);assert r.status_code==202,r.text
    worker.run_once();p=client.get('/api/projects/'+pid).json()
    assert p['jobs'][-1]['state']=='succeeded',p['jobs'][-1]
    result=p['dubbings'][-1];assert result['analysis_id']=='script'
    assert [(s['start_ms'],s['end_ms']) for s in result['segments']]==[(0,500),(520,1020)]
    assert result['segments'][0]['source_ranges'][0]['start_ms']==5000
    assert not any(s['overlap'] or s['overflow_ms'] for s in result['segments'])
    track=next(t for t in p['tracks'] if t['kind']=='review');assert track['cues'][1]['start_ms']==520
    video=client.get(f'/api/projects/{pid}/narrations/{r.json()["job_id"]}/video');assert video.status_code==200
    output=directory/'review.mp4';output.write_bytes(video.content)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)]))
    assert abs(float(probe['format']['duration'])-1.04)<.12
    assert next(s for s in probe['streams'] if s['codec_type']=='video')['width']==640
    assert hashlib.sha256(media.read_bytes()).hexdigest()==checksum
    response=client.get(f'/api/projects/{pid}/tracks/{track["id"]}/export?format=srt');assert '00:00:00,520' in response.text
    response=client.post(f'/api/projects/{pid}/render',json={'revision':p['revision'],'asset_id':aid,'track_id':track['id'],'burn_subtitles':True})
    assert response.status_code==422 and 'timeline' in response.text
    calls=len(state['requests']);body['revision']=p['revision'];r=client.post(f'/api/projects/{pid}/narrations',json=body)
    assert r.status_code==202;worker.run_once();assert len(state['requests'])==calls
