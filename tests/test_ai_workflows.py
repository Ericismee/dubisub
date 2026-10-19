"""Controlled protocol fixtures, NOT live AI quality verification."""
import re
import json
import threading
import subprocess
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import store,worker
from backend.subtitles import parse


@pytest.fixture
def provider(tmp_path,monkeypatch):
    state={'requests':[],'fail_batch':False,'bad_ids':False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def respond(self,value,status=200):
            content=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def do_GET(self):
            if self.path=='/api/tags':self.respond({'models':[{'name':'fixture-model'}]});return
            if self.path.endswith('/voices'):
                self.respond({'data':[{'id':'fixture-vi','name':'Fixture VI','gender':'female','languages':['vi']},{'id':'fixture-en','name':'Fixture EN','gender':'male','languages':['en']}]});return
            self.respond({'data':[{'id':'fixture-model'}]})
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']))
            if self.path.endswith('/speech'):
                import io,wave
                state['requests'].append({'tts':True,'voice':json.loads(raw)['voice']})
                audio=io.BytesIO()
                with wave.open(audio,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\x00\x00'*8000)
                content=audio.getvalue();self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
            if self.path.endswith('/transcriptions'):
                state['requests'].append({'asr':True,'has_wav':b'RIFF' in raw,'iso_language':b'\r\nvi\r\n' in raw})
                self.respond({'segments':[{'start':.1,'end':.7,'text':'ASR fixture: Xin chÃ o'}]});return
            body=json.loads(raw)
            content=body['messages'][-1]['content']
            if isinstance(content,str) and content.startswith('Return JSON only: '):
                value=json.loads(content.removeprefix('Return JSON only: '));self.respond({'choices':[{'message':{'content':json.dumps(value)}}]});return
            if isinstance(content,list):
                data=json.loads(content[0]['text']);state['requests'].append({'vision':True,'frames':data['frames']})
                value={'items':[{'text':'Fixture: visible test pattern','evidence_ids':list(data['frames'])}]}
                self.respond({'choices':[{'message':{'content':json.dumps(value)}}]});return
            data=json.loads(content);state['requests'].append(data)
            if state.get('rate_limit_once'):
                state['rate_limit_once']=False;self.respond({'error':'fixture-rate-limit'},429);return
            if 'evidence' in data:
                value={'items':[{'text':'Fixture summary only','evidence_ids':list(data['evidence'])[:2]}]}
                self.respond({'choices':[{'message':{'content':json.dumps(value)}}]});return
            if state['fail_batch'] and len(data['cues'])<20:
                state['fail_batch']=False;self.respond({'error':'fixture'},500);return
            cues=[{'id':c['id'],'text':f'fixture-{data["target_language"]}: '+(re.sub('[\u3400-\u9fff]','',c['text']) if data['target_language'].startswith('vi') else c['text'])} for c in data['cues']]
            if state.get('han_once'):
                state['han_once']=False;cues[0]['text']='chưa dịch 房子'
            if state['bad_ids'] or state.get('bad_language')==data['target_language']:cues[0]['id']='wrong'
            if self.path=='/api/chat':
                assert body['stream'] is False and body['format']=='json'
                self.respond({'message':{'content':json.dumps({'cues':cues})}});return
            self.respond({'choices':[{'message':{'content':json.dumps({'cues':cues})}}]})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path/'db'))
    try:
        with TestClient(app) as client:
            client.put('/api/settings',json={'providers':[{'kind':kind,'endpoint':f'http://127.0.0.1:{server.server_port}/v1','model':'fixture-model','key_env':''} for kind in ('asr','translation','tts')]})
            yield client,state,tmp_path
    finally:server.shutdown();server.server_close();thread.join()


def source(client,count=2):
    pid=client.post('/api/projects',json={'name':'AI fixture'}).json()['id']
    text='\n\n'.join(f'{i+1}\n00:00:{i:02},100 --> 00:00:{i:02},900\nBonjour ä¸–ç•Œ {i}' for i in range(count))
    client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('fixture.srt',text.encode())})
    return client.get('/api/projects/'+pid).json()


def test_multilingual_translation_original_intact_and_review(provider):
    client,state,_=provider;p=source(client);pid=p['id'];track=p['tracks'][0]
    checks=client.post('/api/providers/translation/check').json();assert checks['connected'] and not checks['inference_verified']
    p=client.put(f'/api/projects/{pid}/glossary',json={'revision':p['revision'],'entries':{'Bonjour':'ChÃ o'}}).json()
    response=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':track['id'],'target_languages':['vi','EN-us']})
    assert response.status_code==202,response.text
    assert worker.run_once() and worker.run_once()
    p=client.get('/api/projects/'+pid).json();assert len(p['tracks'])==3
    assert p['tracks'][0]==track
    for t in p['tracks'][1:]:
        assert [c['id'] for c in t['cues']]==[c['id'] for c in track['cues']]
        assert [c['start_ms'] for c in t['cues']]==[c['start_ms'] for c in track['cues']]
        assert not t['reviewed']
        for fmt in ('srt','vtt','ass'):
            r=client.get(f'/api/projects/{pid}/tracks/{t["id"]}/export?format={fmt}');assert r.status_code==200
            assert parse(r.text,fmt)[0]['text']==t['cues'][0]['text']
    assert state['requests'][0]['glossary']=={'Bonjour':'ChÃ o'}
    tid=p['tracks'][1]['id']
    p=client.put(f'/api/projects/{pid}/tracks/{tid}/review',json={'revision':p['revision'],'reviewed':True}).json()
    assert p['tracks'][1]['reviewed']
    cues=p['tracks'][0]['cues'];cues[0]['text']='source changed'
    client.put(f'/api/projects/{pid}/tracks/{track["id"]}',json={'revision':p['revision'],'cues':cues})
    p=client.get('/api/projects/'+pid).json();assert p['tracks'][1]['source_changed']
    assert client.put(f'/api/projects/{pid}/tracks/{tid}/review',json={'revision':p['revision'],'reviewed':True}).status_code==409


def test_checkpoint_retry_and_strict_output(provider):
    client,state,_=provider;p=source(client,25);pid=p['id'];state['fail_batch']=True
    jid=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi']}).json()['jobs'][0]['id']
    worker.run_once();p=client.get('/api/projects/'+pid).json();assert p['jobs'][0]['state']=='failed'
    assert len(p['tracks'])==1
    with store.connect() as db:assert json.loads(db.execute('SELECT checkpoint FROM jobs WHERE id=?',(jid,)).fetchone()[0])['next_batch']==1
    assert client.post('/api/jobs/'+jid+'/retry').status_code==200
    worker.run_once();p=client.get('/api/projects/'+pid).json();assert p['jobs'][0]['state']=='succeeded'
    assert len(state['requests'])==3 and len(p['tracks'])==2
    state['bad_ids']=True
    client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['ja']})
    worker.run_once();p=client.get('/api/projects/'+pid).json();assert p['jobs'][-1]['state']=='failed' and len(p['tracks'])==2


def test_asr_real_audio_iso_language_and_manual_track(provider):
    client,state,directory=provider
    audio=directory/'Ã¢m thanh thá»­.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1','-y',str(audio)],check=True)
    pid=client.post('/api/projects',json={'name':'ASR fixture'}).json()['id']
    with audio.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':(audio.name,f)})
    worker.run_once();p=client.get('/api/projects/'+pid).json()
    response=client.post(f'/api/projects/{pid}/transcribe',json={'asset_id':p['assets'][0]['id'],'source_language':'vi-VN'})
    assert response.status_code==202,response.text
    worker.run_once();p=client.get('/api/projects/'+pid).json()
    assert p['jobs'][-1]['state']=='succeeded',p['jobs']
    assert p['tracks'][0]['cues'][0]['start_ms']==100 and p['tracks'][0]['cues'][0]['end_ms']==700
    track=p['tracks'][0];original=client.get(f'/api/projects/{pid}/tracks/{track["id"]}/asr-original').json()['cues']
    edited=[{**c,'text':'User correction'} for c in track['cues']]
    client.put(f'/api/projects/{pid}/tracks/{track["id"]}',json={'revision':p['revision'],'cues':edited})
    assert client.get(f'/api/projects/{pid}/tracks/{track["id"]}/asr-original').json()['cues']==original
    p=client.get('/api/projects/'+pid).json()
    assert state['requests'][0]['has_wav'] and state['requests'][0]['iso_language']
    r=client.post(f'/api/projects/{pid}/tracks',json={'revision':p['revision'],'language':'ja'})
    assert r.status_code==201
    assert r.json()['project']['tracks'][-1]['cues']==[]


def test_missing_provider_not_mocked(tmp_path,monkeypatch):
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path))
    with TestClient(app) as client:
        p=source(client)
        assert client.post(f'/api/projects/{p["id"]}/translate',json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi']}).status_code==409
        assert not client.get('/api/projects/'+p['id']).json()['jobs']


def test_one_target_failure_does_not_discard_other_target(provider):
    client,state,_=provider;p=source(client);pid=p['id'];state['bad_language']='vi'
    r=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi','en']})
    assert r.status_code==202
    worker.run_once();worker.run_once()
    p=client.get('/api/projects/'+pid).json()
    assert [j['state'] for j in p['jobs']]==['failed','succeeded']
    assert p['tracks'][-1]['language']=='en'


def test_voice_discovery_sample_cache_and_language_guard(provider):
    client,state,_=provider;p=source(client);pid=p['id']
    voices=client.get('/api/voices').json()['voices']
    assert voices[0]['languages']==['vi'] and voices[1]['languages']==['en']
    assert client.post(f'/api/projects/{pid}/voice-samples',json={'voice_id':'fixture-vi','language':'en'}).status_code==422
    response=client.post(f'/api/projects/{pid}/voice-samples',json={'voice_id':'fixture-vi','language':'vi'})
    assert response.status_code==202,response.text
    sample=response.json()['sample_id'];worker.run_once()
    p=client.get('/api/projects/'+pid).json();assert p['jobs'][-1]['state']=='succeeded',p['jobs']
    assert sample in p['voice_samples']
    audio=client.get(f'/api/projects/{pid}/voice-samples/{sample}');assert audio.status_code==200 and audio.content.startswith(b'RIFF')
    assert client.post(f'/api/projects/{pid}/voice-samples',json={'voice_id':'fixture-vi','language':'vi'}).json()['ready']
    assert len([r for r in state['requests'] if r.get('tts')])==1


def test_ollama_native_translation_and_catalog(provider):
    client,state,_=provider
    configs=client.get('/api/settings').json()['providers']
    config=next(p for p in configs if p['kind']=='translation')
    response=client.put('/api/settings',json={'providers':[{'kind':'translation','endpoint':config['endpoint'],'model':'fixture-model','protocol':'ollama'}]})
    assert response.status_code==200
    check=client.post('/api/providers/translation/check').json()
    assert check['models']==['fixture-model'] and not check['inference_verified']
    catalog=client.get('/api/provider-catalog').json()
    assert len(catalog['models'])>18 and not catalog['installed_verified']
    p=source(client)
    r=client.post(f"/api/projects/{p['id']}/translate",json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi']})
    assert r.status_code==202
    assert worker.run_once()
    result=client.get('/api/projects/'+p['id']).json()
    assert result['tracks'][-1]['cues'][0]['text'].startswith('fixture-vi:')
    assert client.put('/api/settings',json={'providers':[{'kind':'tts','endpoint':config['endpoint'],'protocol':'ollama'}]}).status_code==422


def test_voice_catalog_rejects_malformed_provider_metadata(monkeypatch):
    from backend import voices
    from backend.providers import ProviderError
    monkeypatch.setattr(voices,'request',lambda config,path,**kw: {'data':[{'id':'v','languages':42}]} if path=='voices' else {'data':[]})
    with pytest.raises(ProviderError,match='Metadata'):voices.catalog({})
    monkeypatch.setattr(voices,'request',lambda config,path,**kw: {'data':[{'id':'v','languages':['vi']}]} if path=='voices' else [])
    with pytest.raises(ProviderError,match='model'):voices.catalog({})
    monkeypatch.setattr(voices,'request',lambda config,path,**kw: {'data':[{'id':'v','languages':'vi'}]} if path=='voices' else {'data':[]})
    assert voices.catalog({})[0]['languages']==['vi']


def test_selected_cue_translation_and_recoverable_track_delete(provider):
    client,state,_=provider;p=source(client);pid=p['id'];original=p['tracks'][0];cue=original['cues'][1]
    r=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':original['id'],'target_languages':['vi'],'cue_ids':[cue['id']]})
    assert r.status_code==202,r.text
    assert worker.run_once()
    p=client.get('/api/projects/'+pid).json();translated=p['tracks'][-1]
    assert p['tracks'][0]==original
    assert [c['id'] for c in translated['cues']]==[cue['id']]
    assert translated['cues'][0]['start_ms']==cue['start_ms']
    r=client.post(f"/api/projects/{pid}/tracks/{original['id']}/archive",json={'revision':p['revision']})
    assert r.status_code==200,r.text
    p=r.json();assert len(p['tracks'])==1 and p['archived_tracks'][0]==original
    assert not p['tracks'][0]['reviewed']
    stale=client.post(f'/api/projects/{pid}/tracks/restore-last',json={'revision':p['revision']-1})
    assert stale.status_code==409
    r=client.post(f'/api/projects/{pid}/tracks/restore-last',json={'revision':p['revision']})
    assert r.status_code==200 and r.json()['tracks'][-1]==original


def test_wrong_asr_model_blocked_before_network():
    from backend.providers import request,ProviderError
    with pytest.raises(ProviderError,match='faster-whisper'):
        request({'endpoint':'http://127.0.0.1:1','model':'nomic-embed-text:latest'},'audio/transcriptions',files={})


def test_untranslated_han_repaired_without_changing_ids_or_context(provider):
    client,state,_=provider;p=source(client);original=p['tracks'][0]
    state['han_once']=True
    r=client.post(f"/api/projects/{p['id']}/translate",json={'revision':p['revision'],'track_id':original['id'],'target_languages':['vi'],'context_note':'Known relationship, not extra dialogue.'})
    assert r.status_code==202
    worker.run_once();result=client.get('/api/projects/'+p['id']).json()
    assert result['jobs'][-1]['state']=='succeeded',result['jobs'][-1]
    translated=result['tracks'][-1]
    assert [(c['id'],c['start_ms'],c['end_ms']) for c in translated['cues']]==[(c['id'],c['start_ms'],c['end_ms']) for c in original['cues']]
    assert len(state['requests'])==2
    assert all(r['context_note']=='Known relationship, not extra dialogue.' for r in state['requests'])


def test_han_validation_only_allows_explicit_glossary_values():
    from backend.ai_tasks import validate_target_text
    from backend.providers import ProviderError
    with pytest.raises(ProviderError):validate_target_text([{'text':'Ngôi nhà 房子'}],'vi')
    validate_target_text([{'text':'Tên gốc 静香'}],'vi',{'Shizuka':'静香'})


def test_batch_cache_metrics_invalidation_and_quality(provider):
    client,state,_=provider;p=source(client,8);pid=p['id'];source_track=p['tracks'][0]
    def run(quality='balanced'):
        current=client.get('/api/projects/'+pid).json()
        r=client.post(f'/api/projects/{pid}/translate',json={'revision':current['revision'],'track_id':source_track['id'],'target_languages':['vi'],'batch_size':2,'quality':quality,'concurrency':2})
        assert r.status_code==202,r.text
        worker.run_once();result=client.get('/api/projects/'+pid).json()
        assert result['jobs'][-1]['state']=='succeeded',result['jobs'][-1]
        return result['jobs'][-1]['metrics']
    first=run();assert first['requests']==4 and first['cache_hits']==0
    count=len(state['requests']);second=run();assert len(state['requests'])==count and second['requests']==0 and second['cache_hits']==4
    with store.connect() as db:
        doc=store.project(db,pid);doc['tracks'][0]['cues'][0]['text']='Changed spoken words';store.save(db,doc)
    changed=run();assert changed['requests']==3 and changed['cache_hits']==1
    careful=run('careful');assert careful['requests']==8 and careful['cache_hits']==0 and careful['proofread_seconds']>=0


def test_rate_limit_backoff_is_bounded_and_measured(provider):
    client,state,_=provider;p=source(client);state['rate_limit_once']=True
    r=client.post(f"/api/projects/{p['id']}/translate",json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi']})
    assert r.status_code==202;worker.run_once();result=client.get('/api/projects/'+p['id']).json();metrics=result['jobs'][-1]['metrics']
    assert result['jobs'][-1]['state']=='succeeded' and metrics['requests']==2 and metrics['rate_limit_retries']==1


def test_partial_translation_is_an_independent_editable_copy(provider):
    client,state,_=provider;p=source(client,25);pid=p['id'];state['fail_batch']=True
    r=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':p['tracks'][0]['id'],'target_languages':['vi']})
    jid=r.json()['jobs'][0]['id'];worker.run_once();p=client.get('/api/projects/'+pid).json()
    assert p['jobs'][-1]['state']=='failed' and p['jobs'][-1]['completed_cues']==20
    response=client.post(f'/api/jobs/{jid}/partial-track',json={'revision':p['revision']});assert response.status_code==201,response.text
    tid=response.json()['track_id']
    with store.connect() as db:
        doc=store.project(db,pid);draft=next(t for t in doc['tracks'] if t['id']==tid);draft['cues'][0]['text']='User edit preserved';store.save(db,doc)
    client.post(f'/api/jobs/{jid}/retry');worker.run_once();p=client.get('/api/projects/'+pid).json()
    assert next(t for t in p['tracks'] if t['id']==tid)['cues'][0]['text']=='User edit preserved'
    assert any(len(t['cues'])==25 and t.get('kind')=='translation' and t['id']!=tid for t in p['tracks'])


def test_translation_uses_nearby_visual_context_and_short_ids(provider):
    client,state,_=provider;p=source(client,3);pid=p['id'];source_track=p['tracks'][0]
    scenes={'id':'scene-test','kind':'scenes','scope':'frame_sampling','items':[
      {'text':'A job interview in an office','source_ranges':[{'start_ms':1000,'end_ms':1001,'type':'image'}]},
      {'text':'Unrelated far-away scene','source_ranges':[{'start_ms':100000,'end_ms':100001,'type':'image'}]}]}
    with store.connect() as db:
        doc=store.project(db,pid);doc['analyses']={'scene-test':scenes};store.save(db,doc)
    p=client.get('/api/projects/'+pid).json()
    r=client.post(f'/api/projects/{pid}/translate',json={'revision':p['revision'],'track_id':source_track['id'],'target_languages':['vi'],'cue_ids':[source_track['cues'][1]['id']],'scene_analysis_id':'scene-test','context_note':'Use consistent character names.'})
    assert r.status_code==202,r.text
    worker.run_once();p=client.get('/api/projects/'+pid).json();translated=p['tracks'][-1]
    prompt=state['requests'][-1]
    assert prompt['cues'][0]['id']=='C1'
    assert len(prompt['context_before'])==1 and len(prompt['context_after'])==1
    assert [v['observation'] for v in prompt['visual_context']]==['A job interview in an office']
    assert translated['cues'][0]['id']==source_track['cues'][1]['id']
    assert translated['translation_context']['scope']=='dialogue_and_sampled_frames'
    with store.connect() as db:
        doc=store.project(db,pid);doc['analyses']['scene-test']['items'][0]['text']='Corrected scene';store.save(db,doc)
    p=client.get('/api/projects/'+pid).json();assert p['tracks'][-1]['source_changed']
    assert client.put(f"/api/projects/{pid}/tracks/{translated['id']}/review",json={'revision':p['revision'],'reviewed':True}).status_code==409
