"""Durable orchestration of existing ASR/translation/export jobs; no browser polling dependency."""
import json
import time
import shutil
from uuid import uuid5,NAMESPACE_URL
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,field_validator
from . import store
from .providers import configured,signature,ProviderError
from .capabilities import verified
from .ai_tasks import fingerprint
from .workflows import tag
router=APIRouter(prefix='/api')

class Plan(BaseModel):
    revision:int
    mode:Literal['translate','summary','review','describe']='translate'
    asset_id:str|None=None
    track_id:str|None=None
    source_language:str='auto'
    targets:list[str]=Field(default_factory=lambda:['vi'],min_length=1,max_length=8)
    force_asr:bool=False
    use_vision:bool=False
    style:Literal['natural','formal','concise']='natural'
    spoiler:Literal['none','limited','full']='limited'
    target_duration_s:int=Field(default=60,ge=10,le=3600)
    condense:bool=False
    output:Literal['draft','subtitles']='draft'
    confirmed:bool=False
    consent_signature:str=''
    @field_validator('targets')
    @classmethod
    def target_tags(cls,values):
        values=[tag(v) for v in values]
        if len(set(values))!=len(values):raise ValueError('Ngôn ngữ đích trùng nhau.')
        return values
    @field_validator('source_language')
    @classmethod
    def source_tag(cls,value):return value if value=='auto' else tag(value)

def plan_for(pid,body):
    with store.connect() as db:
        doc=store.project(db,pid)
        row=db.execute("SELECT * FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,pid)).fetchone() if body.asset_id else None
    if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã thay đổi. Lưu/mở lại trước khi lập pipeline.')
    media=dict(row) if row else None;meta=json.loads(media['metadata']) if media and media.get('metadata') else {}
    if body.asset_id and not media:raise HTTPException(422,'Nguồn media không thuộc dự án hoặc đã bị xóa.')
    chosen=next((t for t in doc['tracks'] if t['id']==body.track_id),None)
    if body.track_id and not chosen:raise HTTPException(422,'Track đã chọn không tồn tại.')
    if chosen and chosen.get('kind') in ('review','description'):raise HTTPException(422,'Caption AI và lời dẫn review không phải lời thoại nguồn. Chọn transcript hoặc phụ đề lời thoại.')
    if not chosen and not body.force_asr:
        candidates=[t for t in doc['tracks'] if t.get('kind','source') not in ('translation','review','description') and t['cues']]
        attached=[t for t in candidates if t.get('asset_id')==body.asset_id]
        if attached:chosen=attached[0]
        elif len(candidates)==1:chosen=candidates[0]
        elif len(candidates)>1:raise HTTPException(422,'Có nhiều track nguồn. Hãy chọn rõ track cần dùng.')
    need_asr=body.force_asr or not chosen and body.mode!='describe'
    configs={};blockers=[];stages=[];transfers=[]
    if body.mode!='translate' and body.output=='subtitles':blockers.append('Kịch bản/caption AI cần duyệt và căn timeline trước khi tạo phụ đề. Chọn bản nháp; xuất Markdown/JSON trong mục Phân tích.')
    if not body.asset_id and (not chosen or not chosen.get('asset_id')):blockers.append('Auto cần nguồn file/link hoặc track đã nhập từ file; chỉnh sửa/xuất track thủ công vẫn dùng được.')
    if need_asr:
        if not any(s.get('codec_type')=='audio' for s in meta.get('streams',[])):blockers.append('Không có audio đã probe để ASR. Chọn phụ đề có sẵn hoặc bật vision cho mô tả.')
        try:
            configs['asr']=configured('asr');transfers.append({'role':'ASR','endpoint':configs['asr']['endpoint'],'model':configs['asr']['model'],'data':'Audio mono 16 kHz theo chunk; trả timestamp thực.'})
        except ProviderError as e:blockers.append(str(e))
        stages.append('asr')
    if body.mode=='describe' and not body.use_vision:blockers.append('Mô tả video ít lời cần vision; không dùng suy đoán từ track rỗng.')
    if body.use_vision:
        if not any(s.get('codec_type')=='video' for s in meta.get('streams',[])):blockers.append('Vision cần nguồn video đã probe.')
        try:
            configs['vision']=configured('vision')
            if not verified(configs['vision'],'image'):blockers.append('Model Vision chưa qua kiểm tra image inference. Không gửi frame vào model text-only.')
            transfers.append({'role':'Vision','endpoint':configs['vision']['endpoint'],'model':configs['vision']['model'],'data':'Các frame JPEG có timecode (sampling, không phải toàn video) và transcript liên quan.'})
        except ProviderError as e:blockers.append(str(e))
        stages.append('vision')
    try:
        configs['translation']=configured('translation')
        if not verified(configs['translation'],'text'):blockers.append('Model LLM chưa qua kiểm tra text/JSON inference. Liệt kê model chưa đủ để chạy Auto.')
        transfers.append({'role':'LLM','endpoint':configs['translation']['endpoint'],'model':configs['translation']['model'],'data':'Transcript/glossary hoặc kết quả cảnh; không gửi video gốc.'})
    except ProviderError as e:blockers.append(str(e))
    stages.append('translate' if body.mode=='translate' else 'analyze')
    if body.output=='subtitles':stages.append('export')
    # Source/model/settings hashes bind consent and prevent changed inputs being sent silently.
    digest=fingerprint({'request':body.model_dump(exclude={'confirmed','consent_signature'}),'providers':configs,'source':fingerprint(chosen['cues']) if chosen and not body.force_asr else media.get('checksum') if media else None,'glossary':doc.get('glossary',{})})
    return {'signature':digest,'stages':stages,'transfers':transfers,'blockers':blockers,'source_track_id':chosen['id'] if chosen and not body.force_asr else None,'source_hash':fingerprint(chosen['cues']) if chosen and not body.force_asr else None,'source':chosen if chosen and not body.force_asr else None,'providers':configs,'glossary':doc.get('glossary',{}),'asset_id':body.asset_id or (chosen['asset_id'] if chosen else None),'cost':'Chưa có bảng giá/token được xác minh; không ước tính chi phí giả.','scope':'frame_sampling' if body.use_vision else 'transcript_only'}

@router.post('/projects/{pid}/auto/plan')
def preview(pid:str,body:Plan):
    result=plan_for(pid,body)
    return {k:v for k,v in result.items() if k not in ('providers','source','glossary')}

@router.post('/projects/{pid}/auto',status_code=202)
def start(pid:str,body:Plan):
    result=plan_for(pid,body)
    if result['blockers']:raise HTTPException(422,'; '.join(result['blockers']))
    if not body.confirmed or body.consent_signature!=result['signature']:raise HTTPException(409,'Xem lại pipeline và xác nhận provider/dữ liệu; nguồn hoặc cấu hình có thể đã đổi.')
    pipeline={'id':store.uid(),'state':'running','stage_index':0,'stages':result['stages'],'steps':{},'created_at':time.time(),'request':body.model_dump(),'plan':result,'error':None,'outputs':[]}
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án vừa thay đổi.')
        running=db.execute("SELECT project_id FROM pipelines WHERE json_extract(document,'$.state')='running' LIMIT 20").fetchall()
        if any(r[0]==pid for r in running):raise HTTPException(409,'Dự án đã có pipeline đang chạy; chờ hoàn tất hoặc hủy trước khi tạo lượt mới.')
        if len(running)>=20:raise HTTPException(409,'Đã đủ 20 pipeline chờ/chạy; chờ worker xử lý trước khi thêm.')
        db.execute('INSERT INTO pipelines VALUES(?,?,?)',(pipeline['id'],pid,json.dumps(pipeline)))
    return {'id':pipeline['id'],'state':'running'}

@router.get('/projects/{pid}/auto')
def listing(pid:str):
    with store.connect() as db:
        store.project(db,pid);rows=db.execute('SELECT document FROM pipelines WHERE project_id=? ORDER BY rowid DESC LIMIT 100',(pid,)).fetchall()
    with store.connect() as db:doc=store.project(db,pid)
    result=[]
    for row in rows:
        p=json.loads(row[0]);item={k:v for k,v in p.items() if k not in ('plan','request')}
        item['outputs']=[{'job_id':jid,**f} for jid,entry in doc.get('auto_exports',{}).items() if entry.get('pipeline_id')==p['id'] for f in entry['files']]
        result.append(item)
    return result

@router.post('/projects/{pid}/auto/{pipeline_id}/{action}')
def control(pid:str,pipeline_id:str,action:Literal['cancel','retry']):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');store.project(db,pid);row=db.execute('SELECT document FROM pipelines WHERE id=? AND project_id=?',(pipeline_id,pid)).fetchone()
        if not row:raise KeyError(pipeline_id)
        p=json.loads(row[0])
        if action=='cancel':
            if p['state']!='running':raise HTTPException(409,'Chỉ hủy pipeline đang chạy.')
            p['state']='canceled'
            for step in p['steps'].values():
                for jid in step['job_ids']:db.execute("UPDATE jobs SET state='canceled' WHERE id=? AND state IN ('queued','running')",(jid,))
        else:
            if p['state'] not in ('failed','canceled'):raise HTTPException(409,'Pipeline chưa thất bại/hủy.')
            ids=p['steps'].get(str(p['stage_index']),{}).get('job_ids',[])
            for jid in ids:
                job=db.execute('SELECT state,attempts FROM jobs WHERE id=?',(jid,)).fetchone()
                if job and job['state'] in ('failed','canceled'):
                    if job['attempts']>=3:raise HTTPException(409,'Tác vụ đã hết 3 lần thử.')
                    db.execute("UPDATE jobs SET state='queued',error=NULL WHERE id=?",(jid,))
            p.update(state='running',error=None)
        db.execute('UPDATE pipelines SET document=? WHERE id=?',(json.dumps(p),pipeline_id))
    return {'state':p['state']}

def tick():
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');rows=db.execute("SELECT * FROM pipelines WHERE json_extract(document,'$.state')='running' ORDER BY rowid LIMIT 20").fetchall()
        for row in rows:
            p=json.loads(row['document'])
            if p['state']!='running':continue
            try:
                doc=store.project(db,row['project_id']);plan=p['plan'];index=p['stage_index'];stage=p['stages'][index]
                if plan.get('source_track_id'):
                    source=next((t for t in doc['tracks'] if t['id']==plan['source_track_id']),None)
                    if not source or fingerprint(source['cues'])!=plan['source_hash']:raise ValueError('Nguồn phụ đề đã đổi. Pipeline dừng để bảo toàn chỉnh sửa; lập kế hoạch mới.')
                key=str(index);step=p['steps'].get(key)
                if step:
                    jobs=[db.execute('SELECT state,error FROM jobs WHERE id=?',(jid,)).fetchone() for jid in step['job_ids']]
                    if any(not j or j['state'] in ('failed','canceled') for j in jobs) and not any(j and j['state'] in ('queued','running') for j in jobs):raise ValueError(next((j['error'] for j in jobs if j and j['error']),'Tác vụ con đã hủy hoặc không còn tồn tại.'))
                    if all(j['state']=='succeeded' for j in jobs):
                        if stage=='asr':
                            source=next((t for t in doc['tracks'] if t.get('job_id') in step['job_ids']),None)
                            if not source:raise ValueError('ASR hoàn tất nhưng chưa có track nguồn.')
                            plan.update(source=source,source_track_id=source['id'],source_hash=fingerprint(source['cues']))
                        if stage=='translate':p['track_ids']=list(dict.fromkeys(p.get('track_ids',[])+[t['id'] for t in doc['tracks'] if t.get('job_id') in step['job_ids']]))
                        if stage=='vision':plan['scenes']=doc.get('analyses',{}).get(step['job_ids'][0])
                        p['stage_index']+=1
                        if p['stage_index']==len(p['stages']):p['state']='draft' if p['request']['output']=='draft' else 'succeeded'
                    else:p['progress']=round((index+sum(j['state']=='succeeded' for j in jobs)/max(1,len(jobs)))/len(p['stages'])*100)
                else:
                    aid=plan['asset_id'];payloads=[]
                    if stage=='asr':
                        media=db.execute('SELECT metadata FROM assets WHERE id=?',(aid,)).fetchone();meta=json.loads(media[0]);stream=next(s for s in meta['streams'] if s.get('codec_type')=='audio');offset=max(0,round((float(stream.get('start_time',0))-float(meta.get('format',{}).get('start_time',0)))*1000))
                        payloads=[('transcribe',{'provider':plan['providers']['asr'],'source_language':p['request']['source_language'],'audio_stream':0,'asset_id':aid,'source_offset_ms':offset})]
                    elif stage=='translate':
                        source=plan['source'];payloads=[('translate',{'source':source,'target_language':language,'provider':plan['providers']['translation'],'glossary':plan['glossary'],'style':p['request'].get('style','natural'),'condense':p['request'].get('condense',False)}) for language in p['request']['targets'] if language!=source.get('language')]
                        if source.get('language') in p['request']['targets']:p['track_ids']=[source['id']]
                    elif stage=='export':payloads=[('auto_export',{'track_ids':p.get('track_ids',[]),'track_hashes':{t['id']:fingerprint(t['cues']) for t in doc['tracks'] if t['id'] in p.get('track_ids',[])},'pipeline_id':p['id']})]
                    elif stage=='vision':payloads=[('vision',{'provider':plan['providers']['vision'],'language':p['request']['targets'][0]})]
                    elif stage=='analyze':payloads=[('analyze',{'provider':plan['providers']['translation'],'source':plan.get('source'),'scenes':plan.get('scenes'),'mode':p['request']['mode'],'language':p['request']['targets'][0],'style':p['request'].get('style','natural'),'spoiler':p['request'].get('spoiler','limited'),'target_duration_s':p['request'].get('target_duration_s',60)})]
                    ids=[]
                    for number,(kind,payload) in enumerate(payloads):
                        jid=str(uuid5(NAMESPACE_URL,f"dubisub:{p['id']}:{index}:{number}"));payload['pipeline_id']=p['id']
                        db.execute('INSERT OR IGNORE INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,?,?)',(jid,row['project_id'],aid,kind,json.dumps(payload)));ids.append(jid)
                    p['steps'][key]={'stage':stage,'job_ids':ids}
            except (ValueError,KeyError,StopIteration) as e:
                p.update(state='failed',error=str(e) if isinstance(e,ValueError) else 'Nguồn pipeline không còn hợp lệ.')
                for step in p['steps'].values():
                    for jid in step['job_ids']:db.execute("UPDATE jobs SET state='canceled' WHERE id=? AND state IN ('queued','running')",(jid,))
            db.execute('UPDATE pipelines SET document=? WHERE id=?',(json.dumps(p),p['id']))

def export_job(job):
    from .subtitles import export
    payload=json.loads(job['payload']);directory=store.root()/'auto-exports'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,job['project_id'])
        if not db.execute("SELECT 1 FROM jobs WHERE id=? AND owner=? AND state='running'",(job['id'],job['owner'])).fetchone():raise ValueError('Đã hủy xuất phụ đề.')
        files=[]
        for tid in payload['track_ids']:
            track=next(t for t in doc['tracks'] if t['id']==tid)
            if payload.get('track_hashes',{}).get(tid)!=fingerprint(track['cues']):raise ValueError('Track đích đã sửa sau khi xếp lịch xuất. Xuất thủ công hoặc lập pipeline mới.')
            for fmt in ('srt','vtt','ass'):
                filename=f'{tid}.{fmt}';content=export(track['cues'],fmt)
                if shutil.disk_usage(directory).free<len(content.encode('utf-8'))+128*1024**2:raise ValueError('Không đủ đĩa để xuất phụ đề Auto.')
                partial=directory/(filename+'.part');partial.write_text(content,encoding='utf-8');partial.replace(directory/filename);files.append({'track_id':tid,'format':fmt,'filename':filename,'language':track['language']})
        doc.setdefault('auto_exports',{})[job['id']]={'files':files,'pipeline_id':payload['pipeline_id']};store.save(db,doc)
        db.execute("UPDATE jobs SET state='succeeded',progress=100,error=NULL WHERE id=?",(job['id'],))

@router.get('/projects/{pid}/auto-exports/{jid}/{tid}/{fmt}')
def download(pid:str,jid:str,tid:str,fmt:Literal['srt','vtt','ass']):
    from fastapi.responses import FileResponse
    with store.connect() as db:doc=store.project(db,pid)
    item=next((f for f in doc.get('auto_exports',{}).get(jid,{}).get('files',[]) if f['track_id']==tid and f['format']==fmt),None)
    if not item:raise KeyError(tid)
    return FileResponse(store.root()/'auto-exports'/jid/item['filename'],filename='dubisub-'+item['language']+'.'+fmt)
