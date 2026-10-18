"""Model-list discovery is distinct from explicitly consented inference probes."""
import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from . import store
from .providers import configured,signature,chat_json,ProviderError
router=APIRouter(prefix='/api')

def record(config,capability,evidence):
    key=signature(config)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT document FROM provider_checks WHERE signature=?',(key,)).fetchone()
        doc=json.loads(row[0]) if row else {'capabilities':{},'attempts':{}}
        doc.setdefault('capabilities',{})[capability]={'verified':True,'evidence':evidence,'at':time.time()}
        db.execute('INSERT INTO provider_checks VALUES(?,?) ON CONFLICT(signature) DO UPDATE SET document=excluded.document',(key,json.dumps(doc)))

def verified(config,capability):
    with store.connect() as db:row=db.execute('SELECT document FROM provider_checks WHERE signature=?',(signature(config),)).fetchone()
    return bool(row and json.loads(row[0]).get('capabilities',{}).get(capability,{}).get('verified'))

@router.get('/providers/{kind}/capabilities')
def status(kind:Literal['asr','translation','vision','tts']):
    config=configured(kind,require_model=False)
    with store.connect() as db:row=db.execute('SELECT document FROM provider_checks WHERE signature=?',(signature(config),)).fetchone()
    result=json.loads(row[0]) if row else {'state':'not_tested','capabilities':{}}
    return {k:v for k,v in result.items() if k not in ('owner','config') }|{'signature':signature(config),'endpoint':config['endpoint'],'model':config.get('model'),'video_native':False}

class Probe(BaseModel):
    capability:Literal['text','image']
    confirmed:bool=False

@router.post('/providers/{kind}/probe',status_code=202)
def enqueue(kind:Literal['translation','vision'],body:Probe):
    if not body.confirmed:raise HTTPException(422,'Xác nhận gửi prompt/ảnh kiểm tra tổng hợp đến provider đã chọn. Không gửi media dự án.')
    config=configured(kind);key=signature(config)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT document FROM provider_checks WHERE signature=?',(key,)).fetchone()
        doc=json.loads(row[0]) if row else {'capabilities':{},'attempts':{}}
        if doc.get('state') in ('queued','running'):raise HTTPException(409,'Đang kiểm tra model này.')
        if doc.get('attempts',{}).get(body.capability,0)>=3:raise HTTPException(409,'Đã thử capability này 3 lần. Kiểm tra cấu hình/model trước khi thử cấu hình mới.')
        doc.update(state='queued',requested=body.capability,config=config,error=None)
        db.execute('INSERT INTO provider_checks VALUES(?,?) ON CONFLICT(signature) DO UPDATE SET document=excluded.document',(key,json.dumps(doc)))
    return {'signature':key,'state':'queued'}

def infer(config,cap):
    nonce=uuid4().hex
    if cap=='text':
        answer=chat_json(config,[{'role':'user','content':'Return JSON only: '+json.dumps({'nonce':nonce,'ok':True})}])
        if answer!={'nonce':nonce,'ok':True}:raise ProviderError('Model không hoàn thành kiểm tra JSON/text.')
    else:
        # Randomized color order makes text-only guessing insufficient evidence.
        import secrets
        colors=secrets.SystemRandom().sample(['red','blue','green','yellow','white'],3)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'probe.jpg'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f"color=c={colors[0]}:s=600x200:d=0.1",'-vf',f"drawbox=x=200:y=0:w=200:h=200:color={colors[1]}:t=fill,drawbox=x=400:y=0:w=200:h=200:color={colors[2]}:t=fill",'-frames:v','1','-y',str(path)],check=True,timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            image=base64.b64encode(path.read_bytes()).decode()
        answer=chat_json(config,[{'role':'user','content':'Inspect this image of three colored rectangles. Return exactly JSON with one key colors and a list of the three color names from left to right, in lowercase English.'}],images=[image])
        if answer!={'colors':colors}:raise ProviderError('Model chưa vượt kiểm tra ảnh; không bật vision từ danh sách model.')
    return {'verified':True,'evidence':'synthetic_inference_probe','at':time.time()}

def run_probe(owner):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');rows=db.execute('SELECT * FROM provider_checks').fetchall();selected=None
        for row in rows:
            doc=json.loads(row['document'])
            if doc.get('state')=='queued' or doc.get('state')=='running' and time.time()-doc.get('started',0)>60:
                if doc.get('attempts',{}).get(doc['requested'],0)>=3:
                    doc.update(state='failed',error='Đã hết 3 lần thử kiểm tra capability.')
                    db.execute('UPDATE provider_checks SET document=? WHERE signature=?',(json.dumps(doc),row['signature']));continue
                selected=(row['signature'],doc);break
        if not selected:return False
        key,doc=selected;cap=doc['requested'];doc.update(state='running',owner=owner,started=time.time());doc['attempts'][cap]=doc['attempts'].get(cap,0)+1
        db.execute('UPDATE provider_checks SET document=? WHERE signature=?',(json.dumps(doc),key))
    try:
        result=subprocess.run([sys.executable,'-m','backend.capabilities',key],capture_output=True,timeout=35,check=True)
        outcome=json.loads(result.stdout)
    except Exception:outcome={'error':'Kiểm tra inference thất bại/hết thời gian. Chưa xác minh capability.'}
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');current=json.loads(db.execute('SELECT document FROM provider_checks WHERE signature=?',(key,)).fetchone()[0])
        if current.get('owner')!=owner or current.get('state')!='running':return True
        current.update(state='failed' if 'error' in outcome else 'succeeded',error=outcome.get('error'))
        if 'error' not in outcome:current.setdefault('capabilities',{})[cap]=outcome
        db.execute('UPDATE provider_checks SET document=? WHERE signature=?',(json.dumps(current),key))
    return True

if __name__=='__main__':
    try:
        with store.connect() as db:doc=json.loads(db.execute('SELECT document FROM provider_checks WHERE signature=?',(sys.argv[1],)).fetchone()[0])
        print(json.dumps(infer(doc['config'],doc['requested'])))
    except ProviderError as e:print(json.dumps({'error':str(e)}))
    except Exception:print(json.dumps({'error':'Không xác minh được inference của model.'}))
