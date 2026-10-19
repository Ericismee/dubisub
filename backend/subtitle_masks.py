"""Reviewed OCR regions in source coordinates, never inferred transcript cues."""
import json
import math
import os
import sys
import hashlib
import shutil
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from . import store
from .ai_tasks import fingerprint

router=APIRouter(prefix='/api')


def regions(rows,duration):
    if not isinstance(rows,list) or len(rows)>3000:raise ValueError('Tối đa 3000 vùng chữ; hãy chọn đoạn ngắn hơn.')
    result=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Vùng chữ không hợp lệ.')
        start,end=row.get('start_ms'),row.get('end_ms')
        if type(start) is not int or type(end) is not int or not 0<=start<end<=duration:raise ValueError('Mốc vùng chữ phải nằm trong nguồn.')
        box={k:row.get(k) for k in ('x','y','width','height')}
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in box.values()):raise ValueError('Tọa độ vùng chữ cần số hữu hạn.')
        if not (0<=box['x']<1 and 0<=box['y']<1 and .001<=box['width']<=1 and .001<=box['height']<=1 and box['x']+box['width']<=1.000001 and box['y']+box['height']<=1.000001):raise ValueError('Vùng chữ phải nằm trong khung nguồn.')
        confidence=row.get('confidence',0)
        if not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:raise ValueError('Confidence vùng chữ không hợp lệ.')
        result.append({'id':str(row.get('id',''))[:100],'start_ms':start,'end_ms':end,**box,'confidence':confidence,'needs_review':bool(row.get('needs_review',True))})
    return sorted(result,key=lambda r:(r['start_ms'],r['y'],r['x']))


def attach(doc,asset_id,mask,duration):
    if not mask.get('track_id'):return mask
    track=doc.get('subtitle_masks',{}).get(mask['track_id'])
    if not track or track['asset_id']!=asset_id or not track.get('reviewed'):raise ValueError('Chọn vùng chữ đã duyệt cho đúng video nguồn.')
    return {**mask,'mode':'tracked','enabled':True,'regions':regions(track['regions'],duration)}


class Detect(BaseModel):
    asset_id:str
    revision:int
    start_ms:int=Field(default=0,ge=0)
    end_ms:int=Field(gt=0)
    fps:int=Field(default=2,ge=1,le=4)
    detector_profile:Literal['cpu_fast','balanced']='cpu_fast'
    roi:dict=Field(default_factory=lambda:{'x':0.,'y':.6,'width':1.,'height':.35})


@router.post('/projects/{pid}/subtitle-masks',status_code=202)
def detect(pid:str,body:Detect):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã đổi; tải lại trước khi dò chữ.')
        asset=db.execute("SELECT * FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,pid)).fetchone()
        meta=json.loads(asset['metadata']) if asset and asset['metadata'] else {}
        video=next((s for s in meta.get('streams',[]) if s.get('codec_type')=='video'),None)
        duration=round(float(meta.get('format',{}).get('duration',0))*1000)
        if not video or not 0<=body.start_ms<body.end_ms<=duration:raise HTTPException(422,'Chọn khoảng nằm trong video đã kiểm tra.')
        if (body.end_ms-body.start_ms)*body.fps>2400000:raise HTTPException(422,'Mỗi lượt tối đa 2400 frame OCR. Chọn vùng ngắn hơn hoặc giảm tần suất có chủ đích.')
        regions([{'start_ms':0,'end_ms':duration,**body.roi}],duration)
        if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND kind='subtitle_mask' AND state IN ('queued','running')",(pid,)).fetchone():raise HTTPException(409,'Đang dò chữ cho dự án này.')
        runtime=Path(os.getenv('DUBISUB_OCR_PYTHON',store.root()/'vieneu-runtime/.venv/Scripts/python.exe'))
        if not runtime.is_file():raise HTTPException(422,'Chưa có runtime OCR local. Xem docs/VIENEU_LOCAL.md; không gửi video ra ngoài.')
        model_dir=runtime.resolve().parents[1]/'Lib/site-packages/rapidocr_onnxruntime/models'
        models=sorted(model_dir.glob('*.onnx'))
        if not models:raise HTTPException(422,'Runtime OCR thiếu model RapidOCR đã cài; chưa gửi tác vụ.')
        model_hashes={p.name:hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in models}
        jid=store.uid();payload={**body.model_dump(),'model_hashes':model_hashes,'checksum':asset['checksum'],'duration_ms':duration,'runtime':str(runtime.resolve()),'detector_version':2}
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'subtitle_mask',?)",(jid,pid,body.asset_id,json.dumps(payload)))
    return {'job_id':jid}


class Edit(BaseModel):
    revision:int
    regions:list[dict]=Field(max_length=3000)
    reviewed:bool=False


@router.put('/projects/{pid}/subtitle-masks/{mid}')
def edit(pid:str,mid:str,body:Edit):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid);track=doc.get('subtitle_masks',{}).get(mid)
        if not track:raise KeyError(mid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã đổi; tải lại trước khi sửa vùng chữ.')
        track['regions']=regions(body.regions,track['duration_ms']);track['reviewed']=body.reviewed;store.save(db,doc)
    return {'revision':doc['revision']}


def execute(job,command):
    payload=json.loads(job['payload']);directory=store.root()/'mask-staging'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    key=fingerprint({k:v for k,v in payload.items() if k!='runtime'});cache=store.root()/'mask-cache';cache.mkdir(exist_ok=True);cached=cache/f'{key}.json'
    if not cached.exists():
        if shutil.disk_usage(directory).free<128*1024**2:raise ValueError('Không đủ dung lượng dự phòng để dò và lưu vùng chữ.')
        from .review_scenes import detect as cuts
        boundaries=cuts(job,command,payload['duration_ms'])
        units=list(range(payload['start_ms'],payload['end_ms'],10000));all_regions=[];data={}
        for index,start in enumerate(units):
            part=directory/f'part-{index:04}.json'
            if not part.exists():
                request={**payload,'start_ms':start,'end_ms':min(start+10000,payload['end_ms']),'path':job['path'],'boundaries':boundaries};input_file=directory/'input.json';input_file.write_text(json.dumps(request),encoding='utf-8')
                result=command([payload['runtime'],str(Path(__file__).resolve().parents[1]/'scripts/detect_subtitle_masks.py'),str(input_file)],job,timeout=600)
                parsed=json.loads(result);parsed['regions']=regions(parsed['regions'],payload['duration_ms']);part.write_text(json.dumps(parsed),encoding='utf-8')
            data=json.loads(part.read_text(encoding='utf-8'));all_regions.extend({**r,'id':f'{index}:{r["id"]}'} for r in data['regions'])
            with store.connect() as db:
                if not db.execute("UPDATE jobs SET progress=?,checkpoint=? WHERE id=? AND owner=? AND state='running'",(10+round(80*(index+1)/len(units)),json.dumps({'completed_chunks':index+1,'total_chunks':len(units)}),job['id'],job['owner'])).rowcount:raise ValueError('Đã hủy dò chữ.')
        data={**data,'regions':regions(all_regions,payload['duration_ms'])};(directory/'result.json').write_text(json.dumps(data),encoding='utf-8');(directory/'result.json').replace(cached)
    data=json.loads(cached.read_text(encoding='utf-8'))
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM jobs WHERE id=? AND owner=? AND state='running'",(job['id'],job['owner'])).fetchone():raise ValueError('Đã hủy dò chữ.')
        doc=store.project(db,job['project_id']);doc.setdefault('subtitle_masks',{})[job['id']]={**data,'id':job['id'],'asset_id':job['asset_id'],'duration_ms':payload['duration_ms'],'source_checksum':payload['checksum'],'reviewed':False,'scope':{'start_ms':payload['start_ms'],'end_ms':payload['end_ms'],'fps':payload['fps'],'roi':payload['roi']},'limitations':'OCR lấy mẫu, có thể sót chữ ngắn/chuyển động hoặc nhận nhầm chữ trong cảnh. Chỉ vùng dò đã chọn; không xóa chữ bằng AI.'};store.save(db,doc)
        db.execute("UPDATE jobs SET state='succeeded',progress=100 WHERE id=?",(job['id'],))
