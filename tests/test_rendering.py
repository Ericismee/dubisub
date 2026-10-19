import hashlib
import json
import subprocess

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import store,worker
from backend.rendering import normalize_plan,output_cues


def test_render_plan_mapping():
    plan=normalize_plan({'in_ms':1000,'out_ms':3000,'speed':2,'aspect':'9:16','resolution':360},4000)
    assert plan['duration_ms']==1000 and (plan['width'],plan['height'])==(360,640)
    result=output_cues([{'id':'a','start_ms':500,'end_ms':1200,'text':'Chào'},{'id':'b','start_ms':2000,'end_ms':4000,'text':'世界'}],plan)
    assert [(c['id'],c['start_ms'],c['end_ms']) for c in result]==[('a',0,100),('b',500,1000)]
    with pytest.raises(ValueError):normalize_plan({'in_ms':-1},4000)
    with pytest.raises(ValueError):normalize_plan({'speed':float('nan')},4000)


def test_ass_text_cannot_inject_override_tags():
    from backend.subtitles import export,parse
    text=export([{'id':'a','start_ms':0,'end_ms':1000,'text':r'{\pos(1,1)} literal \N'}],'ass')
    event=text.splitlines()[-1]
    assert '{' not in event and '}' not in event and r'\pos' not in event
    assert 'literal' in parse(text,'ass')[0]['text']


@pytest.mark.parametrize('burn',[False,True])
def test_real_export_trim_speed_canvas_audio_and_subtitle(tmp_path,monkeypatch,burn):
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path/'dữ liệu render'))
    source=tmp_path/'nguồn có khoảng trắng.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=24:d=1',
      '-f','lavfi','-i','color=c=green:s=320x180:r=24:d=1','-f','lavfi','-i','color=c=blue:s=320x180:r=24:d=1',
      '-f','lavfi','-i','sine=frequency=440:duration=3','-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]',
      '-map','[v]','-map','3:a','-c:v','libx264','-c:a','aac','-pix_fmt','yuv420p','-y',str(source)],check=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    with TestClient(app) as client:
        pid=client.post('/api/projects',json={'name':'Render fixture'}).json()['id']
        with source.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':(source.name,f)})
        worker.run_once()
        client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('sub.srt','1\n00:00:01,200 --> 00:00:01,800\nChào render\n'.encode())})
        p=client.get('/api/projects/'+pid).json()
        body={'revision':p['revision'],'asset_id':p['assets'][0]['id'],'track_id':p['tracks'][0]['id'],'burn_subtitles':burn,
              'plan':{'in_ms':1000,'out_ms':3000,'speed':2,'aspect':'9:16','resolution':360,'volume':.5}}
        result=client.post(f'/api/projects/{pid}/render',json=body)
        assert result.status_code==202,result.text
        assert worker.run_once()
        p=client.get('/api/projects/'+pid).json();assert p['jobs'][-1]['state']=='succeeded',p['jobs']
        item=p['artifacts'][0];r=client.get(f'/api/projects/{pid}/artifacts/{item["id"]}');assert r.status_code==200 and r.headers['content-type']=='video/mp4'
        path=store.root()/'artifacts'/f'{item["id"]}.mp4'
        meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
        v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
        assert (v['width'],v['height'])==(360,640)
        assert abs(float(meta['format']['duration'])-1)<.15
        assert abs(float(a['duration'])-float(v['duration']))<.15
        # Subtitle-only render must retain audible source after the cue ends.
        from array import array
        samples=array('h',subprocess.check_output(['ffmpeg','-v','error','-ss','0.8','-i',str(path),'-t','0.15','-f','s16le','-ac','1','pipe:1']))
        assert sum(x*x for x in samples)/max(1,len(samples))>10000
        for position,channel in ((.25,1),(.75,2)):
            pixel=subprocess.check_output(['ffmpeg','-v','error','-ss',str(position),'-i',str(path),'-vf','crop=2:2:179:319,scale=1:1','-frames:v','1','-pix_fmt','rgb24','-threads','1','-f','rawvideo','pipe:1'])
            assert pixel[channel]==max(pixel) and pixel[channel]>pixel[0]
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
