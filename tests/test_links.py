import contextlib
import functools
import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import store, worker, link_tasks
from backend.safe_http import SafeHTTP, NetworkPolicyError
from backend.link_sources import inspect_source, extractor, youtube_url, public_info


@pytest.fixture
def fixture_source(tmp_path):
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_HEAD(self):
            if self.path=='/fallback.vtt':
                self.send_response(405);self.end_headers();return
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','http://127.0.0.1/private');self.end_headers();return
            super().do_HEAD()
        def do_GET(self):
            if self.path=='/fallback.vtt':
                self.send_response(206);self.send_header('Content-Length','1');self.send_header('Content-Range','bytes 0-0/100');self.end_headers();self.wfile.write(b'W');return
            if self.path=='/resume.mp4':
                payload=b'1234567890';start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0])
                self.send_response(206 if start else 200);self.send_header('ETag','"fixture"');self.send_header('Content-Length',str(len(payload)-start))
                if start:self.send_header('Content-Range',f'bytes {start}-9/10')
                self.end_headers();self.wfile.write(payload[start:]);return
            if self.path=='/oversize.mp4':
                self.send_response(200);self.send_header('Content-Length','9999999999');self.end_headers();return
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','http://127.0.0.1/private');self.end_headers();return
            super().do_GET()
    (tmp_path/'sample.vtt').write_text('WEBVTT\n\n00:00:00.100 --> 00:00:01.000\nChào từ link 世界\n',encoding='utf-8')
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(tmp_path)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=('http','127.0.0.1',server.server_port)
    try:yield f'http://127.0.0.1:{server.server_port}',origin,tmp_path
    finally:server.shutdown();server.server_close();thread.join()


def test_private_and_rebinding_policy(monkeypatch):
    for url in ('http://127.0.0.1/x','http://169.254.169.254/','http://[::1]/','file:///etc/passwd','http://user:password@example.com/'):
        with pytest.raises(NetworkPolicyError):SafeHTTP().validate(url)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',80)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',80))])
    with pytest.raises(NetworkPolicyError):SafeHTTP().validate('http://public.example/')


def test_redirect_size_and_extractor_policy(fixture_source):
    url,origin,directory=fixture_source
    safe=SafeHTTP(test_origin=origin)
    with pytest.raises(NetworkPolicyError):safe.open(url+'/redirect')
    with pytest.raises(ValueError):link_tasks.stream_file(safe,url+'/oversize.mp4',directory/'part',100)
    with extractor(SafeHTTP()) as ydl:
        assert list(ydl._request_director.handlers)==['Guarded']
        from yt_dlp.networking import Request
        with pytest.raises(Exception):ydl.urlopen(Request('http://127.0.0.1/private'))
    assert youtube_url('https://youtu.be/BaW_jenozKc?t=3')=='https://www.youtube.com/watch?v=BaW_jenozKc'
    with pytest.raises(ValueError):youtube_url('https://www.youtube.com/watch?v=BaW_jenozKc&list=xxx')
    info=inspect_source(url+'/fallback.vtt',SafeHTTP(test_origin=origin))
    assert info['source']=='direct' and info['subtitles'][0]['id']=='direct'
    part=directory/'resume.part';part.write_bytes(b'123');part.with_suffix('.validator').write_text('"fixture"')
    assert link_tasks.stream_file(SafeHTTP(test_origin=origin),url+'/resume.mp4',part,10)==10
    assert part.read_bytes()==b'1234567890'


def test_real_link_subtitle_job_and_export(fixture_source,monkeypatch):
    url,origin,directory=fixture_source
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(directory/'db'))
    with TestClient(app) as client:
        p=client.post('/api/projects',json={'name':'Link fixture'}).json();pid=p['id']
        result=client.post(f'/api/projects/{pid}/links',json={'url':url+'/sample.vtt?token=hidden'}).json()
        executor=lambda jid:link_tasks.execute(jid,SafeHTTP(test_origin=origin))
        assert worker.run_once(link_executor=executor)
        info=client.get('/api/links/'+result['link_id']).json()
        assert info['jobs'][0]['state']=='succeeded',info
        assert 'hidden' not in json.dumps(info)
        assert client.post('/api/links/'+result['link_id']+'/download',json={'mode':'subtitles','subtitle_ids':['direct']}).status_code==202
        assert worker.run_once(link_executor=executor)
        p=client.get('/api/projects/'+pid).json()
        assert p['tracks'][0]['cues'][0]['text']=='Chào từ link 世界'
        tid=p['tracks'][0]['id']
        assert 'Chào từ link 世界' in client.get(f'/api/projects/{pid}/tracks/{tid}/export').text
        assert client.post('/api/links/'+result['link_id']+'/download',json={'mode':'subtitles','subtitle_ids':['direct']}).status_code==409
        assert not list((store.root()/'staging').glob('*'))


def test_production_worker_blocks_local_source(tmp_path,monkeypatch):
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(tmp_path))
    with TestClient(app) as client:
        pid=client.post('/api/projects',json={'name':'blocked'}).json()['id']
        link=client.post(f'/api/projects/{pid}/links',json={'url':'http://127.0.0.1/private.mp4'}).json()
        assert worker.run_once()
        state=client.get('/api/links/'+link['link_id']).json()
        assert state['jobs'][0]['state']=='failed'
        assert 'private.mp4' not in state['jobs'][0]['error']


def test_link_video_download_and_probe(fixture_source,monkeypatch):
    import subprocess
    url,origin,directory=fixture_source
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=160x90:d=1','-c:v','libx264','-y',str(directory/'sample.mp4')],check=True)
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(directory/'db'))
    with TestClient(app) as client:
        pid=client.post('/api/projects',json={'name':'Video link'}).json()['id']
        link=client.post(f'/api/projects/{pid}/links',json={'url':url+'/sample.mp4'}).json()['link_id']
        execute=lambda jid:link_tasks.execute(jid,SafeHTTP(test_origin=origin))
        assert worker.run_once(link_executor=execute)
        assert client.post('/api/links/'+link+'/download',json={'mode':'video','format_id':'direct'}).status_code==202
        assert worker.run_once(link_executor=execute)
        assert worker.run_once()
        p=client.get('/api/projects/'+pid).json()
        assert all(j['state']=='succeeded' for j in p['jobs']),p['jobs']
        assert json.loads(p['assets'][0]['metadata'])['streams'][0]['width']==160


def test_youtube_signed_url_refresh_preserves_selection(fixture_source,monkeypatch):
    url,origin,directory=fixture_source
    monkeypatch.setenv('DUBISUB_DATA_DIR',str(directory/'refresh-db'))
    calls=[]
    def inspection(source,client):
        calls.append(source)
        return {'title':'fixture','duration':1,'source':'youtube','source_url':'https://www.youtube.com/watch?v=jNQXAC9IVRw','formats':[], 'subtitles':[{'id':'manual:vi','language':'vi','automatic':False,'ext':'vtt','url':url+'/sample.vtt'}]}
    monkeypatch.setattr(link_tasks,'inspect_source',inspection)
    original=link_tasks.stream_file
    attempts=[]
    def download(client,source,path,cap,**kwargs):
        attempts.append(source)
        if len(attempts)==1:
            path.write_bytes(b'old-representation')
            path.with_suffix('.validator').write_text('old')
            raise link_tasks.DownloadRejected('fixture 403')
        assert not path.exists() and not path.with_suffix('.validator').exists()
        return original(client,source,path,cap,**kwargs)
    monkeypatch.setattr(link_tasks,'stream_file',download)
    with TestClient(app) as c:
        pid=c.post('/api/projects',json={'name':'refresh fixture'}).json()['id']
        lid=c.post(f'/api/projects/{pid}/links',json={'url':'https://youtu.be/jNQXAC9IVRw'}).json()['link_id']
        execute=lambda jid:link_tasks.execute(jid,SafeHTTP(test_origin=origin))
        assert worker.run_once(link_executor=execute)
        assert c.post('/api/links/'+lid+'/download',json={'mode':'subtitles','subtitle_ids':['manual:vi']}).status_code==202
        assert worker.run_once(link_executor=execute)
        state=c.get('/api/links/'+lid).json()
        assert state['jobs'][0]['state']=='succeeded',state
        assert len(calls)==2 and len(attempts)==2
        assert c.get('/api/projects/'+pid).json()['tracks'][0]['cues'][0]['text']=='Chào từ link 世界'
