"""Explicit local stem trials, chunk checkpoints and immutable source audio."""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from . import store
from .ai_tasks import fingerprint

router=APIRouter(prefix='/api')
MODEL_SHA='8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4'
LIMITATIONS='HTDemucs được huấn luyện cho nhạc, chưa chứng minh tối ưu cho thoại phim. Nền là tổng stems không-vocal, có thể còn thoại hoặc mất hiệu ứng; phải nghe mẫu trước khi chạy dài.'


def runtime():return store.root()/'separator-runtime/.venv/Scripts/python.exe'


@router.get('/separation/capabilities')
def capabilities():
    weight=store.root()/'separator-runtime/models/955717e8-8726e21a.th'
    ready=runtime().is_file() and weight.is_file()
    return {'configured':ready,'model':'htdemucs','model_sha256':MODEL_SHA,'device':'cpu','stems':['vocals','background'] if ready else [],'limitations':LIMITATIONS,'inference_verified':False}


class Separate(BaseModel):
    revision:int
    asset_id:str
    audio_stream:int=Field(default=0,ge=0,le=32)
    start_ms:int=Field(default=0,ge=0)
    end_ms:int=Field(gt=0)


@router.post('/projects/{pid}/separations',status_code=202)
def create(pid:str,body:Separate):
    if not capabilities()['configured']:raise HTTPException(422,'Chưa cài runtime/model separation local đã pin. Không gửi media ra dịch vụ ngoài.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã đổi; tải lại trước khi tách audio.')
        asset=db.execute("SELECT * FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,pid)).fetchone();meta=json.loads(asset['metadata']) if asset and asset['metadata'] else {}
        duration=round(float(meta.get('format',{}).get('duration',0))*1000)
        if not 0<=body.start_ms<body.end_ms<=duration or body.end_ms-body.start_ms>1200000:raise HTTPException(422,'Chọn vùng trong nguồn, tối đa20 phút/lượt.')
        if len([s for s in meta.get('streams',[]) if s.get('codec_type')=='audio'])<=body.audio_stream:raise HTTPException(422,'Không có audio track đã chọn.')
        if body.end_ms-body.start_ms>30000 and not any(s['asset_id']==body.asset_id and s.get('reviewed') and s.get('audio_stream')==body.audio_stream and s.get('model_sha256')==MODEL_SHA for s in doc.get('audio_stems',{}).values()):raise HTTPException(422,'Tách/nghe và duyệt mẫu tối đa30 giây trước khi xử lý cả video.')
        if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND kind='separate' AND state IN ('queued','running')",(pid,)).fetchone():raise HTTPException(409,'Dự án đang tách audio; chờ hoặc hủy trước.')
        jid=store.uid();payload={**body.model_dump(),'source_checksum':asset['checksum'],'model_sha256':MODEL_SHA,'settings':{'device':'cpu','threads':2,'segment_size':5,'shifts':0,'overlap':.25,'join_crossfade_ms':1000,'version':1}}
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'separate',?)",(jid,pid,body.asset_id,json.dumps(payload)))
    return {'job_id':jid,'limitations':LIMITATIONS}


class Review(BaseModel):
    revision:int
    reviewed:bool=False


@router.put('/projects/{pid}/separations/{sid}/review')
def review(pid:str,sid:str,body:Review):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã đổi; tải lại trước khi duyệt stems.')
        stem=doc.get('audio_stems',{}).get(sid)
        if not stem:raise KeyError(sid)
        stem['reviewed']=body.reviewed;store.save(db,doc)
    return {'revision':doc['revision']}


@router.get('/projects/{pid}/separations/{sid}/{kind}')
def audio(pid:str,sid:str,kind:Literal['vocals','background']):
    with store.connect() as db:doc=store.project(db,pid)
    if sid not in doc.get('audio_stems',{}):raise KeyError(sid)
    return FileResponse(store.root()/'stems'/f'{sid}-{kind}.wav',media_type='audio/wav')


def execute(job,command):
    from .worker import FORMATS
    payload=json.loads(job['payload']);key=fingerprint(payload);cache=store.root()/'separation-cache'/key;cache.mkdir(parents=True,exist_ok=True)
    duration=payload['end_ms']-payload['start_ms'];started=time.perf_counter()
    if shutil.disk_usage(cache).free<duration/1000*48000*4*6+256*1024**2:raise ValueError('Thiếu dung lượng dự phòng để tách audio. Không sửa file nguồn.')
    directory=store.root()/'separation-staging'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    units=list(range(payload['start_ms'],payload['end_ms'],30000));outputs={k:[] for k in ('vocals','background')};process_seconds=0.;hits=0
    for index,start in enumerate(units):
        paths={k:cache/f'{index:04d}-{k}.wav' for k in outputs}
        begin=max(payload['start_ms'],start-500);end=min(payload['end_ms'],start+30500)
        import wave
        def valid(path):
            try:
                with wave.open(str(path)) as wav:return wav.getnchannels()==2 and wav.getframerate()==48000 and abs(wav.getnframes()/48000*1000-(end-begin))<50
            except (OSError,EOFError,wave.Error):return False
        if not all(valid(p) for p in paths.values()):
            chunk=directory/f'{index:04d}';chunk.mkdir(exist_ok=True);source=chunk/'input.wav'
            command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-ss',str(begin/1000),'-t',str((end-begin)/1000),'-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',job['path'],'-map',f'0:a:{payload["audio_stream"]}','-vn','-ac','2','-ar','44100','-c:a','pcm_s16le','-y',str(source)],job)
            request=chunk/'request.json';request.write_text(json.dumps({'input':str(source),'output_dir':str(chunk)}),encoding='utf-8')
            result=json.loads(command([str(runtime()),str(Path(__file__).resolve().parents[1]/'scripts/separate_audio.py'),str(request)],job,timeout=1800));process_seconds+=result['elapsed_seconds']
            files={k:Path(v).resolve() for k,v in result['files'].items()}
            if any(not p.is_relative_to(chunk.resolve()) for p in files.values()):raise ValueError('Stem không nằm trong staging đã tạo.')
            for kind in outputs:
                temp=chunk/f'{kind}-normalized.wav'
                if kind=='vocals':args=['-i',str(files['vocals']),'-map','0:a:0']
                else:args=['-i',str(files['drums']),'-i',str(files['bass']),'-i',str(files['other']),'-filter_complex','[0:a][1:a][2:a]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.99:level=0:latency=1[mix]','-map','[mix]']
                command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin',*args,'-t',str((end-begin)/1000),'-ac','2','-ar','48000','-c:a','pcm_s16le','-y',str(temp)],job)
                temp.replace(paths[kind])
        else:hits+=1
        for kind,path in paths.items():outputs[kind].append(path)
        with store.connect() as db:
            if not db.execute("UPDATE jobs SET checkpoint=?,progress=? WHERE id=? AND owner=? AND state='running'",(json.dumps({'completed_chunks':index+1,'metrics':{'separation_seconds':process_seconds,'cache_hits':hits}}),10+round(75*(index+1)/len(units)),job['id'],job['owner'])).rowcount:raise ValueError('Đã hủy tách audio.')
    destination=store.root()/'stems';destination.mkdir(exist_ok=True);moved=[]
    try:
        for kind,files in outputs.items():
            temp=directory/f'{kind}.wav';args=[]
            for path in files:args+=['-i',str(path)]
            if len(files)>1:
                graph='';previous='0:a'
                for i in range(1,len(files)):graph+=f'[{previous}][{i}:a]acrossfade=d=1:c1=tri:c2=tri[a{i}];';previous=f'a{i}'
                args+=['-filter_complex',graph.rstrip(';'),'-map',f'[{previous}]']
            command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin',*args,'-t',str(duration/1000),'-ac','2','-ar','48000','-c:a','pcm_s16le','-y',str(temp)],job,timeout=1800)
            import wave
            with wave.open(str(temp)) as wav:
                if wav.getnchannels()!=2 or abs(wav.getnframes()/wav.getframerate()*1000-duration)>50:raise ValueError('Stem không khớp thời lượng nguồn; chưa lưu bản thiếu.')
            target=destination/f'{job["id"]}-{kind}.wav';temp.replace(target);moved.append(target)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute("SELECT 1 FROM jobs WHERE id=? AND owner=? AND state='running'",(job['id'],job['owner'])).fetchone():raise ValueError('Đã hủy tách audio.')
            doc=store.project(db,job['project_id']);doc.setdefault('audio_stems',{})[job['id']]={'id':job['id'],'asset_id':job['asset_id'],'audio_stream':payload['audio_stream'],'start_ms':payload['start_ms'],'end_ms':payload['end_ms'],'model':'htdemucs','model_sha256':MODEL_SHA,'cache_key':key,'reviewed':False,'limitations':LIMITATIONS,'elapsed_seconds':time.perf_counter()-started,'process_seconds':process_seconds,'cache_hits':hits};store.save(db,doc);db.execute("UPDATE jobs SET state='succeeded',progress=100 WHERE id=?",(job['id'],))
    except BaseException:
        for path in moved:path.unlink(missing_ok=True)
        raise
