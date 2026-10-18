"""Provider-driven voice catalog and content-addressed, reusable sample audio."""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import httpx
import langcodes
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from . import store
from .providers import configured,request,ProviderError

router=APIRouter(prefix='/api')


def catalog(provider):
    response=request(provider,'voices',timeout=10)
    rows=response.get('data',response.get('voices')) if isinstance(response,dict) else response
    if not isinstance(rows,list) or len(rows)>1000:raise ProviderError('Provider không trả danh sách giọng hợp lệ.')
    models=request(provider,'models',timeout=10)
    if not isinstance(models,dict) or not isinstance(models.get('data'),list):
        raise ProviderError('Provider không trả danh sách model hợp lệ.')
    vieneu=any(isinstance(m,dict) and m.get('id')=='vieneu-v3-turbo' for m in models.get('data',[]))
    result=[]
    for item in rows:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not 0<len(item['id'])<=160:continue
        # User-enrolled references are project-scoped in DubiSub, never global presets.
        if item['id'].startswith('dubisub_'):continue
        languages=item.get('languages') or ([item['language']] if item.get('language') else ['vi'] if vieneu else [])
        if isinstance(languages,str):languages=[languages]
        if not isinstance(languages,list):raise ProviderError('Metadata ngôn ngữ giọng không hợp lệ.')
        languages=[langcodes.standardize_tag(t) for t in languages if isinstance(t,str) and langcodes.tag_is_valid(t) and t!='und'][:20]
        result.append({'id':item['id'],'name':str(item.get('name') or item['id'])[:160],'gender':item.get('gender') if item.get('gender') in ('male','female') else 'unknown','languages':languages,'description':str(item.get('description',''))[:400]})
    return result


@router.get('/voices')
def voices():
    try:
        provider=configured('tts');return {'voices':catalog(provider),'provider':'configured-tts','model':provider['model']}
    except ProviderError as exc:raise HTTPException(422,str(exc)) from None


class VoiceSample(BaseModel):
    voice_id:str=Field(min_length=1,max_length=160)
    language:str=Field(default='vi',max_length=40)
    text:str|None=Field(default=None,min_length=1,max_length=300)


@router.post('/projects/{project_id}/voice-samples',status_code=202)
def sample(project_id:str,body:VoiceSample):
    try:
        provider=configured('tts');voice=next((v for v in catalog(provider) if v['id']==body.voice_id),None)
        language=langcodes.standardize_tag(body.language)
        if not voice or language not in voice['languages']:raise ProviderError('Giọng này chưa công bố khả năng đọc ngôn ngữ đã chọn.')
    except (ProviderError,langcodes.LanguageTagError) as exc:raise HTTPException(422,str(exc)) from None
    text=body.text or {'vi':'Xin chào! Đây là giọng đọc thử trong DubiSub.','en':'Hello! This is a voice preview in DubiSub.'}.get(language)
    if not text:raise HTTPException(422,'Hãy nhập đoạn nghe thử đúng ngôn ngữ này.')
    payload={'provider':provider,'voice_id':voice['id'],'language':language,'text':text}
    key=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();payload['cache_key']=key
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if (store.root()/'voice-cache'/f'{key}.wav').is_file():
            doc.setdefault('voice_samples',{})[key]={'voice_id':voice['id'],'language':language,'text':text};store.save(db,doc)
            return {'ready':True,'sample_id':key}
        active=db.execute("SELECT id FROM jobs WHERE project_id=? AND kind='voice_sample' AND state IN ('queued','running') AND json_extract(payload,'$.cache_key')=?",(project_id,key)).fetchone()
        if active:return {'ready':False,'job_id':active[0],'sample_id':key}
        aid,jid=store.uid(),store.uid()
        db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,NULL)',(aid,project_id,'Mẫu giọng','','generated',''))
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'voice_sample',?)",(jid,project_id,aid,json.dumps(payload)))
    return {'ready':False,'job_id':jid,'sample_id':key}


@router.get('/projects/{project_id}/voice-samples/{sample_id}')
def audio(project_id:str,sample_id:str):
    with store.connect() as db:doc=store.project(db,project_id)
    if sample_id not in doc.get('voice_samples',{}):raise KeyError(sample_id)
    path=store.root()/'voice-cache'/f'{sample_id}.wav'
    if not path.is_file():raise KeyError(sample_id)
    return FileResponse(path,media_type='audio/wav')


def synthesize(job,command,provider,voice_id,text,directory):
    headers={'Accept':'audio/wav'}
    if provider.get('key_env'):
        value=os.getenv(provider['key_env'])
        if not value:raise ProviderError('Worker chưa có khóa của provider TTS.')
        headers['Authorization']='Bearer '+value
    try:
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=180) as client:
            with client.stream('POST',provider['endpoint'].rstrip('/')+'/audio/speech',headers=headers,json={'model':provider['model'],'voice':voice_id,'input':text,'response_format':'wav'}) as response:
                if response.status_code!=200:raise ProviderError(f'TTS trả HTTP {response.status_code}. Không tự đổi giọng/model.')
                raw=directory/'provider.wav';size=0
                with raw.open('wb') as output:
                    for chunk in response.iter_bytes(65536):
                        size+=len(chunk)
                        if size>20*1024**2 or shutil.disk_usage(directory).free<128*1024**2:raise ProviderError('Mẫu giọng vượt giới hạn hoặc không đủ đĩa.')
                        with store.connect() as db:
                            if not db.execute("SELECT id FROM jobs WHERE id=? AND state='running' AND owner=?",(job['id'],job['owner'])).fetchone():raise ProviderError('Đã hủy tạo mẫu giọng.')
                        output.write(chunk)
        normalized=directory/'sample.wav'
        command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-f','wav','-i',str(raw),'-t','180','-ac','1','-ar','48000','-c:a','pcm_s16le','-y',str(normalized)],job)
        meta=json.loads(command([os.getenv('DUBISUB_FFPROBE','ffprobe'),'-v','error','-show_format','-of','json',str(normalized)],job))
        if not 0<float(meta['format']['duration'])<180:raise ProviderError('Mẫu TTS không chứa audio hợp lệ hoặc quá dài.')
    except httpx.HTTPError:raise ProviderError('Không kết nối được TTS hoặc stream bị gián đoạn.') from None
    return normalized


def execute(job,command):
    payload=json.loads(job['payload']);provider=payload['provider'];key=payload['cache_key']
    directory=store.root()/'voice-staging'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    final=store.root()/'voice-cache'/f'{key}.wav';final.parent.mkdir(exist_ok=True)
    if not final.is_file():
        normalized=synthesize(job,command,provider,payload['voice_id'],payload['text'],directory)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT id FROM jobs WHERE id=? AND state='running' AND owner=?",(job['id'],job['owner'])).fetchone():raise ProviderError('Tác vụ đã hủy.')
        doc=store.project(db,job['project_id'])
        if not final.is_file():normalized.replace(final)
        doc.setdefault('voice_samples',{})[key]={'voice_id':payload['voice_id'],'language':payload['language'],'text':payload['text']};store.save(db,doc)
        db.execute("UPDATE jobs SET state='succeeded',progress=100,error=NULL,checkpoint='sample-cached' WHERE id=?",(job['id'],))
