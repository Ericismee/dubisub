"""Controlled adapters and actual FFmpeg media; no live AI quality claim."""
import json
import subprocess
import wave
import pytest
from test_ai_workflows import provider
from backend import worker,store,dubbing
from backend.providers import configured

def source(client,directory):
    media=directory/'reference.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=8','-c:a','pcm_s16le','-y',str(media)],check=True)
    p=client.post('/api/projects',json={'name':'dubbing fixture'}).json();pid=p['id']
    with media.open('rb') as f:assert client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('fixture.wav',f)}).status_code==202
    assert worker.run_once()
    p=client.get('/api/projects/'+pid).json();return pid,p['assets'][0]['id']

def test_reference_consent_extract_and_delete(provider):
    client,state,directory=provider;pid,aid=source(client,directory)
    body={'asset_id':aid,'name':'Allowed fixture','start_ms':1000,'end_ms':6000,'permission_confirmed':True,'clean_sample_confirmed':True}
    assert client.post(f'/api/projects/{pid}/voice-profiles',json={**body,'permission_confirmed':False}).status_code==422
    assert client.post(f'/api/projects/{pid}/voice-profiles',json={**body,'end_ms':2000}).status_code==422
    r=client.post(f'/api/projects/{pid}/voice-profiles',json=body);assert r.status_code==202,r.text
    assert worker.run_once();profile=r.json()['profile_id'];path=store.root()/'voice-profiles'/f'{profile}.wav'
    with wave.open(str(path)) as audio:assert audio.getnchannels()==1 and audio.getframerate()==48000 and audio.getnframes()==240000
    assert client.get(f'/api/projects/{pid}/voice-profiles/{profile}/audio').content[:4]==b'RIFF'
    assert not state['requests'] # extraction sends no audio to any provider
    assert client.delete(f'/api/projects/{pid}/voice-profiles/{profile}').status_code==200
    assert not path.exists()

def test_narration_checkpoint_cache_timing_and_single_cue(provider,monkeypatch):
    client,state,directory=provider;pid,aid=source(client,directory)
    monkeypatch.setattr(dubbing,'capability',lambda p:{'cloning':True})
    sub='1\n00:00:00,100 --> 00:00:00,300\nHello one\n\n2\n00:00:00,350 --> 00:00:00,550\nHello two\n'
    client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('fixture.srt',sub.encode())})
    p=client.get('/api/projects/'+pid).json();track=p['tracks'][0]
    body={'revision':p['revision'],'track_id':track['id'],'voice':{'kind':'preset','id':'fixture-vi'},'transfer_confirmed':True,'provider_fingerprint':dubbing.fingerprint(configured('tts')),'asset_id':aid}
    monkeypatch.setattr(dubbing,'catalog',lambda provider:[{'id':'fixture-vi','languages':['vi']},{'id':'fixture-alt','languages':['vi']}])
    body.update(speakers={'second':{'kind':'preset','id':'fixture-alt'}},cue_speakers={track['cues'][1]['id']:'second'})
    assert client.post(f'/api/projects/{pid}/narrations',json={**body,'voice':{'kind':'preset','id':'unsupported'}}).status_code==422
    assert client.post(f'/api/projects/{pid}/narrations',json={**body,'transfer_confirmed':False}).status_code==422
    assert client.post(f'/api/projects/{pid}/narrations',json={**body,'provider_fingerprint':'old-provider'}).status_code==409
    original=dubbing.synthesize;calls=[]
    def fail_second(*args):
        calls.append(True)
        if len(calls)==2:raise ValueError('controlled failure')
        return original(*args)
    monkeypatch.setattr(dubbing,'synthesize',fail_second)
    r=client.post(f'/api/projects/{pid}/narrations',json=body);assert r.status_code==202,r.text
    assert worker.run_once();jid=r.json()['job_id'];p=client.get('/api/projects/'+pid).json();assert next(j for j in p['jobs'] if j['id']==jid)['state']=='failed'
    assert client.post('/api/jobs/'+jid+'/retry').status_code==200
    assert worker.run_once();p=client.get('/api/projects/'+pid).json();d=p['dubbings'][-1]
    assert [r['voice'] for r in state['requests'] if r.get('tts')]==['fixture-vi','fixture-alt']
    assert p['narration_settings'][track['id']]['cue_speakers']==body['cue_speakers']
    assert p['narration_settings'][track['id']]['speakers']==body['speakers']
    assert len(calls)==3 and len(d['segments'])==2 # first completed cue reused on retry
    assert d['segments'][0]['overflow_ms']>0 and d['segments'][0]['overlap']
    assert client.get(f'/api/projects/{pid}/narrations/{jid}/audio').content[:4]==b'RIFF'
    r=client.post(f'/api/projects/{pid}/narrations',json={**body,'revision':p['revision'],'cue_ids':[track['cues'][1]['id']]});assert r.status_code==202
    assert worker.run_once();assert len(calls)==3 # no repeated synthesis for identical content

def test_cloning_requires_real_endpoint_contract(monkeypatch):
    from backend.providers import ProviderError
    monkeypatch.setattr(dubbing,'request',lambda *a,**k:{'data':[{'id':'vieneu-v3-turbo'}]} if a[1]=='models' else {'paths':{}})
    with pytest.raises(ProviderError,match='đăng ký'):dubbing.capability({'model':'vieneu-v3-turbo','endpoint':'http://localhost:1/v1'})


def test_pcm_timeline_clipping_and_language(tmp_path,monkeypatch):
    from array import array
    from pydantic import ValidationError
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(dubbing,'active',lambda job:None)
    cache=tmp_path/'dubbing-cache';cache.mkdir()
    for key,value in [('a',10000),('b',30000)]:
        samples=array('h',[value]*48000)
        with wave.open(str(cache/f'{key}.wav'),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000);f.writeframes(samples.tobytes())
    destination=tmp_path/'mix.wav'
    dubbing.mix([{'cache_key':'a','start_ms':0,'duration_ms':1000},{'cache_key':'b','start_ms':500,'duration_ms':1000}],destination,{})
    with wave.open(str(destination)) as f:
        samples=dubbing.pcm_samples(f.readframes(f.getnframes()))
    assert len(samples)==72000 and samples[0]==10000 and samples[30000]==32767 and samples[70000]==30000
    body={'revision':0,'voice':{'kind':'preset','id':'fixture'},'language':'VI-vn'}
    assert dubbing.Narration(**body).language=='vi-VN'
    with pytest.raises(ValidationError):dubbing.Narration(**{**body,'language':'English'})


def test_provider_roles_and_default_vieneu(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import app
    from backend.providers import ProviderError
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path))
    with TestClient(app) as c:
        settings=c.get('/api/settings').json()
        tts=next(p for p in settings['providers'] if p['kind']=='tts')
        assert tts['model']=='vieneu-v3-turbo' and tts['endpoint']=='http://127.0.0.1:8001/v1'
        with pytest.raises(ProviderError,match='ASR'):configured('asr')
        c.put('/api/settings',json={'providers':[{'kind':'translation','protocol':'ollama','endpoint':'https://example.invalid/v1','model':'vieneu-v3-turbo'}]})
        r=c.post('/api/projects/nonexistent/translate',json={'revision':0,'track_id':'none','target_languages':['vi']})
        assert r.status_code==409 and 'VieNeu chỉ dùng' in r.json()['detail']
        c.put('/api/settings',json={'providers':[{'kind':'asr','endpoint':'http://127.0.0.1:11434/v1','model':'nomic-embed-text:latest'}]})
        with pytest.raises(ProviderError,match='embedding'):configured('asr')


def test_fitted_dubbing_burns_measured_subtitles_and_preserves_source(provider,monkeypatch):
    import hashlib
    from backend.subtitles import parse
    client,state,directory=provider
    video=directory/'fit-source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:duration=3','-c:v','libx264','-y',str(video)],check=True)
    checksum=hashlib.sha256(video.read_bytes()).hexdigest()
    pid=client.post('/api/projects',json={'name':'fitted dubbing'}).json()['id']
    with video.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('fit-source.mp4',f)})
    worker.run_once()
    sub='1\n00:00:00,100 --> 00:00:00,300\nFirst speech\n\n2\n00:00:00,500 --> 00:00:00,900\nSecond speech\n'
    client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('fit.srt',sub.encode())})
    p=client.get('/api/projects/'+pid).json();track=p['tracks'][0];aid=next(a['id'] for a in p['assets'] if a['kind']=='media')
    monkeypatch.setattr(dubbing,'capability',lambda provider:{'cloning':True})
    body={'revision':p['revision'],'track_id':track['id'],'voice':{'kind':'preset','id':'fixture-vi'},'transfer_confirmed':True,'provider_fingerprint':dubbing.fingerprint(configured('tts')),'asset_id':aid,'export_video':True,'fit_timing':True,'burn_subtitles':True}
    r=client.post(f'/api/projects/{pid}/narrations',json=body);assert r.status_code==202,r.text
    worker.run_once();p=client.get('/api/projects/'+pid).json();assert p['jobs'][-1]['state']=='succeeded',p['jobs'][-1]
    d=p['dubbings'][-1];assert d['segments'][0]['speed_factor']>1
    assert not any(s['overlap'] or s['overflow_ms'] for s in d['segments'])
    for cue,segment in zip(d['subtitle_cues'],d['segments']):
        assert cue['start_ms']==segment['start_ms'] and cue['end_ms']==segment['start_ms']+segment['duration_ms']
    r=client.get(f"/api/projects/{pid}/narrations/{d['id']}/srt");assert r.status_code==200
    assert len(parse(r.text,'srt'))==2
    assert client.get(f"/api/projects/{pid}/narrations/{d['id']}/video").status_code==200
    assert hashlib.sha256(video.read_bytes()).hexdigest()==checksum
