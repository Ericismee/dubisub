"""Bounded remote tasks. Network downloads never use FFmpeg or external downloaders."""
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from . import store
from .link_sources import inspect_source
from .safe_http import SafeHTTP


def stream_file(client, url, path, cap, headers=None, progress=lambda size,total:None):
    """Resume only if a validator is present and Content-Range exactly matches."""
    validator_path=path.with_suffix('.validator')
    previous=path.stat().st_size if path.exists() else 0
    validator=validator_path.read_text() if validator_path.exists() else ''
    request_headers=dict(headers or {})
    if previous and validator:
        request_headers.update({'Range':f'bytes={previous}-','If-Range':validator})
    else:
        previous=0
    with client.open(url, headers=request_headers) as response:
        if response.status not in (200,206):
            raise ValueError('Nguồn từ chối tải file. Hãy phân tích lại liên kết rồi thử lại.')
        if response.headers.get('Content-Encoding','identity') not in ('identity',''):
            raise ValueError('Định dạng truyền tải nén chưa được hỗ trợ.')
        length=response.headers.get('Content-Length')
        length=int(length) if length and length.isdigit() else None
        if response.status==206:
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
            if not match or int(match[1])!=previous or not validator:
                raise ValueError('Nguồn trả dữ liệu tiếp tục tải không hợp lệ.')
            total=int(match[3])
        else:
            previous=0
            total=length
        if previous>cap or (total is not None and total>cap):
            raise ValueError('File vượt giới hạn dung lượng nhập.')
        new_validator=response.headers.get('ETag') or response.headers.get('Last-Modified') or ''
        validator_path.write_text(new_validator)
        size=previous
        with path.open('ab' if previous else 'wb') as output:
            while chunk:=response.read(256*1024):
                size+=len(chunk)
                if size>cap or shutil.disk_usage(path.parent).free < len(chunk)+64*1024**2:
                    raise ValueError('Vượt giới hạn tải hoặc không đủ dung lượng đĩa dự phòng.')
                output.write(chunk)
                progress(size,total)
        if total is not None and size!=total:
            raise ValueError('Nguồn ngắt tải trước khi hoàn tất. Có thể thử lại.')
        return size


def download_plan(info, selection):
    mode=selection.get('mode','video')
    formats=info.get('formats',[])
    chosen=[]
    if mode!='subtitles':
        selected=next((f for f in formats if f['format_id']==selection.get('format_id')),None)
        if not selected:
            raise ValueError('Chọn một định dạng có trong thông tin nguồn.')
        if mode=='audio' and selected.get('vcodec')!='none':
            raise ValueError('Chọn track chỉ có âm thanh để nhập audio.')
        chosen=[dict(selected,kind='media')]
        if mode=='video' and selected.get('acodec')=='none':
            audio=next((f for f in reversed(formats) if f.get('vcodec')=='none' and f.get('acodec')!='none'),None)
            if audio:chosen.append(dict(audio,kind='audio_merge'))
    subtitles=[]
    for sid in selection.get('subtitle_ids',[]):
        sub=next((s for s in info.get('subtitles',[]) if s['id']==sid),None)
        if not sub:raise ValueError('Phụ đề đã chọn không còn có trong nguồn.')
        subtitles.append(dict(sub,kind='subtitle'))
    if mode=='subtitles' and not subtitles:
        raise ValueError('Chọn ít nhất một track phụ đề để nhập.')
    if len(subtitles)>5:
        raise ValueError('Mỗi lần nhập tối đa 5 track phụ đề.')
    return chosen+subtitles


def execute(job_id, client=None):
    def check():
        with store.connect() as db:
            row=db.execute('SELECT state,owner FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not row or row['state']!='running' or row['owner']!=job['owner']:raise ValueError('Tác vụ đã hủy hoặc bị gián đoạn.')
    with store.connect() as db:
        job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
        link=dict(db.execute('SELECT * FROM link_imports WHERE id=?',(job['asset_id'],)).fetchone())
    client=client or SafeHTTP(check=check,deadline=time.monotonic()+(120 if job['kind']=='inspect_link' else 10800))
    if job['kind']=='inspect_link':
        info=inspect_source(link['url'],client)
        if info.get('duration') and info['duration']>43200:
            raise ValueError('Chỉ nhận media dài tối đa 12 giờ.')
        check()
        with store.connect() as db:
            db.execute('UPDATE link_imports SET inspection=? WHERE id=?',(json.dumps(info),link['id']))
        return {'inspected':True}
    info=json.loads(link['inspection'])
    selection=json.loads(job['payload'])
    plan=download_plan(info,selection)
    directory=store.root()/'staging'/job_id
    directory.mkdir(parents=True,exist_ok=True)
    cap=int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2
    files=[]
    for index,item in enumerate(plan):
        check()
        path=directory/f'{index}.part'
        file_cap=min(cap,8*1024**2) if item['kind']=='subtitle' else cap
        last_update=0
        def progress(size,total):
            nonlocal last_update
            if time.monotonic()-last_update<.5:return
            last_update=time.monotonic()
            value=int(10+75*(index+(size/total if total else 0))/len(plan))
            with store.connect() as db:
                db.execute("UPDATE jobs SET progress=? WHERE id=? AND state='running'",(value,job_id))
        stream_file(client,item['url'],path,file_cap,headers=item.get('http_headers'),progress=progress)
        size=path.stat().st_size
        cap-=size
        if cap<0:raise ValueError('Tổng file vượt giới hạn dung lượng nhập.')
        files.append({'path':str(path),'kind':item['kind'],'ext':item['ext'], 'language':item.get('language') or 'und',
                      'automatic':item.get('automatic',False)})
    return {'files':files,'title':info['title'],'source_url':info['source_url'],'source':info['source']}


if __name__=='__main__':
    try:
        print(json.dumps(execute(sys.argv[1])))
    except Exception as exc:
        # All messages here are ours; exceptions from network libs may contain signed URLs.
        message=str(exc) if type(exc) is ValueError else 'Không tải được nguồn hoặc nguồn bị chặn bởi chính sách mạng.'
        print(json.dumps({'error':message}))
