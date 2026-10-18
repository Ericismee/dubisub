"""A new explicitly confirmed AI run preserves failed jobs and old checkpoints."""
import json
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from . import store
from .providers import configured
from .ai_tasks import fingerprint
router=APIRouter(prefix='/api/job-restarts')

def prepare(db,jid):
    row=db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    if not row:raise KeyError(jid)
    job=dict(row);doc=store.project(db,job['project_id'])
    if job['state'] not in ('failed','canceled') or job['kind'] not in ('transcribe','translate'):raise HTTPException(409,'Chỉ tạo lượt mới cho ASR/dịch đã lỗi hoặc hủy.')
    payload=json.loads(job['payload']);payload.pop('pipeline_id',None)
    payload['provider']=configured('asr' if job['kind']=='transcribe' else 'translation')
    if job['kind']=='translate':
        source=next((t for t in doc['tracks'] if t['id']==payload['source']['id']),None)
        if not source:raise HTTPException(409,'Track nguồn không còn tồn tại.')
        payload.update(source=source,glossary=doc.get('glossary',{}))
    return job,payload,fingerprint({'job_id':jid,'payload':payload})

@router.get('/{jid}')
def plan(jid:str):
    with store.connect() as db:job,payload,signature=prepare(db,jid)
    p=payload['provider']
    return {'signature':signature,'model':p['model'],'provider':'Local trên máy, không gửi audio' if p.get('protocol')=='faster_whisper' else p['endpoint'],'data':'audio của nguồn' if job['kind']=='transcribe' else 'track phụ đề và thuật ngữ'}

class Confirm(BaseModel):
    confirmed:bool=False
    signature:str=''

@router.post('/{jid}',status_code=202)
def restart(jid:str,body:Confirm):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');job,payload,signature=prepare(db,jid)
        if not body.confirmed or body.signature!=signature:raise HTTPException(409,'Cấu hình/nguồn đã đổi. Xem và xác nhận lượt mới trước khi chạy.')
        if db.execute("SELECT 1 FROM jobs WHERE asset_id=? AND kind=? AND state IN ('queued','running')",(job['asset_id'],job['kind'])).fetchone():raise HTTPException(409,'Nguồn đang có tác vụ cùng loại. Chờ hoàn tất hoặc hủy trước.')
        new=store.uid();payload['restart_of']=jid
        db.execute('INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,?,?)',(new,job['project_id'],job['asset_id'],job['kind'],json.dumps(payload)))
    return {'job_id':new}
