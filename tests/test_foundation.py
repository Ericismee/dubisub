import io
import json
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import store, worker
from backend.subtitles import parse, export


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DUBISUB_DATA_DIR', str(tmp_path / 'Dữ liệu có dấu'))
    with TestClient(app) as client:
        yield client


SRT = '\ufeff1\r\n00:00:00,100 --> 00:00:01,200\r\nXin chào Việt Nam!\r\n\r\n2\r\n00:00:01,300 --> 00:00:02,000\r\nمرحبا 世界\r\n'


def create(client):
    result = client.post('/api/projects', json={'name': 'Phim thử nghiệm', 'mode': 'review', 'target_language': 'VI-vn'})
    assert result.status_code == 201, result.text
    return result.json()['id']


def test_edit_reopen_export_conflict(client):
    pid = create(client)
    assert client.get('/health').json()['status'] == 'ok'
    assert client.get('/api/settings').json()['providers'] == []
    assert client.post(f'/api/projects/{pid}/upload', data={'kind': 'subtitle'}, files={'file': ('đường dẫn có dấu.srt', SRT.encode())}).status_code == 202
    p = client.get(f'/api/projects/{pid}').json()
    assert p['target_language'] == 'vi-VN'
    track = p['tracks'][0]
    track['cues'][0]['text'] = 'Đã sửa tiếng Việt\n第二行'
    payload = {'revision': p['revision'], 'cues': track['cues']}
    url = f'/api/projects/{pid}/tracks/{track["id"]}'
    assert client.put(url, json=payload).status_code == 200
    assert client.put(url, json=payload).status_code == 409
    for fmt in ('srt', 'vtt'):
        output = client.get(url + '/export', params={'format': fmt})
        cues = parse(output.text, fmt)
        assert cues[0]['text'] == track['cues'][0]['text']
        assert cues[1]['text'] == 'مرحبا 世界'
        assert cues[0]['start_ms'] == 100
    assert client.get(f'/api/projects/{pid}').json()['tracks'][0]['cues'][0]['id'] == track['cues'][0]['id']


def test_invalid_upload_and_timing(client, monkeypatch):
    pid = create(client)
    url = f'/api/projects/{pid}/upload'
    assert client.post(url, data={'kind': 'subtitle'}, files={'file': ('bad.srt', b'not subtitles')}).status_code == 422
    assert client.post(url, data={'kind': 'media'}, files={'file': ('empty.mp4', b'')}).status_code == 422
    monkeypatch.setenv('DUBISUB_MAX_UPLOAD_MB', '0')
    assert client.post(url, data={'kind': 'media'}, files={'file': ('big.mp4', b'1')}).status_code == 413
    assert not list((store.root()/'assets').iterdir())
    assert client.post('/api/projects', json={'name': 'a', 'target_language': 'Vietnamese'}).status_code == 422


def test_timing_and_duplicate_id_validation(client):
    pid = create(client)
    client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('sample.srt',SRT.encode())})
    p=client.get(f'/api/projects/{pid}').json()
    track=p['tracks'][0]
    url=f'/api/projects/{pid}/tracks/{track["id"]}'
    track['cues'][0]['end_ms']=track['cues'][0]['start_ms']
    assert client.put(url,json={'revision':p['revision'],'cues':track['cues']}).status_code == 422
    track['cues'][0]['end_ms']=1200
    track['cues'][1]['id']=track['cues'][0]['id']
    assert client.put(url,json={'revision':p['revision'],'cues':track['cues']}).status_code == 422


def test_ass_plaintext():
    ass = '[Script Info]\nScriptType: v4.00+\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.10,0:00:01.20,Default,,0,0,0,,{\\b1}Chào\\N世界\n'
    cues = parse(ass, 'ass')
    assert cues[0]['text'] == 'Chào\n世界'


def test_real_ffmpeg_probe_and_extract(client, tmp_path):
    pid = create(client)
    sub = tmp_path/'phụ đề.srt'; sub.write_text(SRT, encoding='utf-8')
    media = tmp_path/'video có khoảng trắng.mkv'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:d=3',
                    '-i',str(sub),'-map','0:v','-map','1:s','-c:v','libx264','-c:s','srt','-y',str(media)], check=True)
    with media.open('rb') as file:
        assert client.post(f'/api/projects/{pid}/upload', data={'kind':'media'}, files={'file':('../video có dấu.mkv',file)}).status_code == 202
    assert worker.run_once()
    p = client.get(f'/api/projects/{pid}').json()
    assert p['jobs'][0]['state'] == 'succeeded', p['jobs']
    assert json.loads(p['assets'][0]['metadata'])['streams'][0]['width'] == 320
    assert p['tracks'][0]['cues'][0]['text'] == 'Xin chào Việt Nam!'
    stream = client.get(f'/api/projects/{pid}/assets/{p["assets"][0]["id"]}/content', headers={'Range':'bytes=0-31'})
    assert stream.status_code == 206 and len(stream.content) == 32
    assert media.exists()


def test_cancel_retry_recovery_and_missing_tool(client, monkeypatch):
    pid = create(client)
    client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('bad.mp4',b'bad media')})
    jid = client.get(f'/api/projects/{pid}').json()['jobs'][0]['id']
    assert client.post(f'/api/jobs/{jid}/cancel').status_code == 200
    assert not worker.run_once()
    assert client.post(f'/api/jobs/{jid}/retry').status_code == 200
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='running',heartbeat=?,attempts=1 WHERE id=?", (time.time()-60,jid))
    monkeypatch.setenv('DUBISUB_FFPROBE', 'dubisub-missing-ffprobe')
    assert worker.run_once()
    p = client.get(f'/api/projects/{pid}').json()
    assert p['jobs'][0]['state'] == 'failed'
    assert p['jobs'][0]['attempts'] == 2
    assert client.post(f'/api/jobs/{jid}/retry').status_code == 200
    worker.run_once()
    assert client.post(f'/api/jobs/{jid}/retry').status_code == 409


def test_worker_running_cancel(client):
    pid = create(client)
    client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('test.mp4',b'bad')})
    with store.connect() as db:
        jid = db.execute('SELECT id FROM jobs').fetchone()[0]
        db.execute("UPDATE jobs SET state='canceled',owner=? WHERE id=?", (worker.OWNER,jid))
    import sys
    with pytest.raises(worker.Canceled):
        worker.command([sys.executable, '-c', 'import time;time.sleep(20)'], {'id':jid})


def test_provider_config_and_local_origin(client, monkeypatch):
    monkeypatch.setenv('DUBISUB_TEST_KEY', 'never-return-this-secret')
    body = {'providers':[{'kind':'translation','endpoint':'http://127.0.0.1:9999/v1','model':'configured-only','key_env':'DUBISUB_TEST_KEY'}]}
    response = client.put('/api/settings',json=body)
    assert response.status_code == 200
    assert response.json()['providers'][0]['verified'] is False
    assert response.json()['providers'][0]['key_present'] is True
    assert 'never-return-this-secret' not in response.text
    assert client.get('/api/settings').json()['ai_status'] == 'unverified'
    assert client.post('/api/projects',json={'name':'evil'},headers={'Origin':'https://untrusted.example'}).status_code == 403
    body['providers'][0]['endpoint'] = 'https://user:secret@example.com/v1?key=secret'
    assert client.put('/api/settings',json=body).status_code == 422


def test_project_edit_delete_restore_preserves_source(client):
    pid=create(client)
    client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('source.mp4',b'source immutable')})
    p=client.get(f'/api/projects/{pid}').json()
    with store.connect() as db:
        source=db.execute('SELECT path FROM assets WHERE project_id=?',(pid,)).fetchone()[0]
    body={'name':'Tên mới 世界','mode':'full','target_language':'en-us','revision':p['revision']}
    response=client.patch('/api/projects/'+pid,json=body)
    assert response.status_code==200
    p=response.json();assert p['name']=='Tên mới 世界' and p['target_language']=='en-US'
    assert client.patch('/api/projects/'+pid,json=body).status_code==409
    assert client.request('DELETE','/api/projects/'+pid,json={'revision':0}).status_code==409
    assert client.request('DELETE','/api/projects/'+pid,json={'revision':p['revision']}).status_code==200
    assert all(p['id']!=pid for p in client.get('/api/projects').json())
    assert client.get('/api/projects/'+pid).status_code==404
    from pathlib import Path
    assert Path(source).read_bytes()==b'source immutable'
    with store.connect() as db:assert db.execute('SELECT state FROM jobs WHERE project_id=?',(pid,)).fetchone()[0]=='canceled'
    assert client.post('/api/projects/'+pid+'/restore').status_code==200
    assert client.get('/api/projects/'+pid).json()['assets'][0]['checksum']
