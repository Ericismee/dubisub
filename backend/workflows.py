"""Versioned workflow endpoints. Jobs snapshot inputs; source tracks remain immutable to AI."""
import json
from typing import Literal

import langcodes
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from . import store
from .providers import configured, check_models, ProviderError

router=APIRouter(prefix='/api')

@router.get('/projects/{project_id}/tracks/{track_id}/asr-original')
def asr_original(project_id:str,track_id:str):
    from fastapi.responses import Response
    with store.connect() as db:doc=store.project(db,project_id)
    track=next((t for t in doc['tracks'] if t['id']==track_id),None)
    if not track or 'raw_cues' not in track:raise KeyError(track_id)
    return Response(json.dumps({'language':track['language'],'cues':track['raw_cues']},ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="dubisub-asr-original.json"'})

@router.get('/provider-catalog')
def provider_catalog():
    from .providers import MODEL_FAMILIES
    return {'models':[{'id':name,'url':'https://ollama.com/library/'+name} for name in MODEL_FAMILIES],'installed_verified':False}


def tag(value):
    if not langcodes.tag_is_valid(value) or value=='und':raise ValueError('Nhập mã ngôn ngữ BCP 47 hợp lệ.')
    return langcodes.standardize_tag(value)


class Translate(BaseModel):
    track_id: str
    target_languages: list[str] = Field(min_length=1,max_length=8)
    revision: int

    @field_validator('target_languages')
    @classmethod
    def targets(cls, values):
        result=[tag(v) for v in values]
        if len(set(result))!=len(result):raise ValueError('Ngôn ngữ đích bị trùng.')
        return result


class Transcribe(BaseModel):
    asset_id: str
    source_language: str='auto'
    audio_stream: int=Field(default=0,ge=0,le=32)

    @field_validator('source_language')
    @classmethod
    def source(cls,value):return value if value=='auto' else tag(value)


class Glossary(BaseModel):
    revision: int
    entries: dict[str,str]=Field(default_factory=dict,max_length=300)

    @field_validator('entries')
    @classmethod
    def entries_valid(cls,values):
        if any(not k.strip() or len(k)>200 or len(v)>500 or '\x00' in k+v for k,v in values.items()):raise ValueError('Thuật ngữ không hợp lệ.')
        if sum(len(k)+len(v) for k,v in values.items())>16000:raise ValueError('Tổng thuật ngữ vượt giới hạn 16.000 ký tự.')
        return values


class Review(BaseModel):
    revision: int
    reviewed: bool


class NewTrack(BaseModel):
    revision:int
    language:str='und'

    @field_validator('language')
    @classmethod
    def language_tag(cls,value):return 'und' if value=='und' else tag(value)


class Render(BaseModel):
    revision:int
    asset_id:str
    track_id:str|None=None
    burn_subtitles:bool=False
    plan:dict=Field(default_factory=dict)


@router.post('/projects/{project_id}/render-plan')
def render_plan(project_id:str,body:Render):
    from .rendering import normalize_plan
    with store.connect() as db:
        doc=store.project(db,project_id)
        row=db.execute("SELECT metadata FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,project_id)).fetchone()
    if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã thay đổi. Hãy lưu trước khi xuất.')
    metadata=json.loads(row[0]) if row and row[0] else {}
    if not any(s.get('codec_type')=='video' for s in metadata.get('streams',[])):raise HTTPException(422,'Chọn nguồn có video đã được kiểm tra.')
    duration=round(float(metadata.get('format',{}).get('duration',0))*1000)
    if duration<=0:raise HTTPException(422,'Chưa xác định được thời lượng video.')
    plan=normalize_plan(body.plan,duration)
    return {'plan':plan}


@router.post('/projects/{project_id}/render',status_code=202)
def render(project_id:str,body:Render):
    plan=render_plan(project_id,body)['plan']
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án vừa thay đổi.')
        track=next((t for t in doc['tracks'] if t['id']==body.track_id),None)
        if body.burn_subtitles and not track:raise HTTPException(422,'Chọn track để gắn phụ đề.')
        if body.burn_subtitles and track.get('kind')=='review':raise HTTPException(422,'Phụ đề review dùng timeline lời dẫn mới; không gắn vào video nguồn. Tải video ở phần Lời dẫn/review.')
        if body.burn_subtitles and track.get('kind') in ('translation','asr') and not track.get('reviewed'):
            raise HTTPException(422,'Hãy duyệt track ASR/bản dịch trước khi gắn vào video.')
        if body.burn_subtitles and track.get('kind')=='translation':
            from .ai_tasks import fingerprint
            source=next((t for t in doc['tracks'] if t['id']==track.get('source_track_id')),None)
            if not source or fingerprint(source['cues'])!=track.get('source_hash'):
                raise HTTPException(422,'Phụ đề nguồn đã thay đổi; dịch và duyệt lại trước khi xuất.')
        jid=store.uid();payload={'plan':plan,'burn_subtitles':body.burn_subtitles,'cues':track['cues'] if track else [],'track_id':body.track_id,'source_revision':doc['revision']}
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'render',?)",(jid,project_id,body.asset_id,json.dumps(payload)))
    return {'job_id':jid,'plan':plan}


@router.post('/projects/{project_id}/tracks',status_code=201)
def create_track(project_id:str,body:NewTrack):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã thay đổi. Mở lại trước khi tạo track.')
        aid,tid=store.uid(),store.uid()
        db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,NULL)',(aid,project_id,'Phụ đề tự tạo','','subtitle',''))
        doc['tracks'].append({'id':tid,'asset_id':aid,'language':body.language,'kind':'manual','cues':[]})
        store.save(db,doc)
    return {'project':doc,'track_id':tid}


@router.post('/providers/{kind}/check')
def provider_check(kind:Literal['asr','translation','vision','tts']):
    try:return check_models(configured(kind,require_model=False))
    except ProviderError as exc:raise HTTPException(422,str(exc)) from None


@router.put('/projects/{project_id}/glossary')
def save_glossary(project_id:str,body:Glossary):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã thay đổi; mở lại trước khi lưu thuật ngữ.')
        doc['glossary']=body.entries;store.save(db,doc)
    return doc


@router.post('/projects/{project_id}/translate',status_code=202)
def translate(project_id:str,body:Translate):
    try:provider=configured('translation')
    except ProviderError as exc:raise HTTPException(409,str(exc)) from None
    jobs=[]
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if doc['revision']!=body.revision:raise HTTPException(409,'Phụ đề đã thay đổi. Hãy lưu và mở lại trước khi dịch.')
        source=next((t for t in doc['tracks'] if t['id']==body.track_id),None)
        if not source or not source['cues']:raise HTTPException(422,'Chọn một track phụ đề có nội dung.')
        if source.get('kind') in ('review','description'):raise HTTPException(422,'Luồng dịch lời thoại không nhận track review/caption AI. Dịch kịch bản cần giữ loại nội dung và timeline riêng.')
        for language in body.target_languages:
            if language==source.get('language'):raise HTTPException(422,'Đích phải khác ngôn ngữ track nguồn.')
            existing=db.execute("SELECT id FROM jobs WHERE project_id=? AND kind='translate' AND state IN ('queued','running') AND json_extract(payload,'$.source.id')=? AND json_extract(payload,'$.target_language')=?",(project_id,source['id'],language)).fetchone()
            if existing:raise HTTPException(409,'Đang có tác vụ dịch cùng track và ngôn ngữ.')
            jid=store.uid();payload={'source':source,'target_language':language,'provider':provider,'glossary':doc.get('glossary',{})}
            db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'translate',?)",(jid,project_id,source['asset_id'],json.dumps(payload)))
            jobs.append({'id':jid,'language':language})
    return {'jobs':jobs}


@router.post('/projects/{project_id}/transcribe',status_code=202)
def transcribe(project_id:str,body:Transcribe):
    try:provider=configured('asr')
    except ProviderError as exc:raise HTTPException(409,str(exc)) from None
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');store.project(db,project_id)
        asset=db.execute("SELECT * FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,project_id)).fetchone()
        if not asset or not asset['metadata']:raise HTTPException(422,'Chờ kiểm tra media hoàn tất.')
        streams=[s for s in json.loads(asset['metadata']).get('streams',[]) if s.get('codec_type')=='audio']
        if body.audio_stream>=len(streams):raise HTTPException(422,'Không tìm thấy track audio đã chọn.')
        if db.execute("SELECT id FROM jobs WHERE asset_id=? AND kind='transcribe' AND state IN ('queued','running')",(body.asset_id,)).fetchone():raise HTTPException(409,'Media đang được nhận dạng.')
        metadata=json.loads(asset['metadata'])
        source_offset=max(0,round((float(streams[body.audio_stream].get('start_time',0))-float(metadata.get('format',{}).get('start_time',0)))*1000))
        jid=store.uid();payload={**body.model_dump(),'provider':provider,'source_offset_ms':source_offset}
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'transcribe',?)",(jid,project_id,body.asset_id,json.dumps(payload)))
    return {'job_id':jid}


@router.put('/projects/{project_id}/tracks/{track_id}/review')
def review_track(project_id:str,track_id:str,body:Review):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,project_id)
        if doc['revision']!=body.revision:raise HTTPException(409,'Track đã thay đổi. Mở lại trước khi duyệt.')
        track=next((t for t in doc['tracks'] if t['id']==track_id),None)
        if not track:raise KeyError(track_id)
        if body.reviewed and track.get('source_track_id'):
            from .ai_tasks import fingerprint
            source=next((t for t in doc['tracks'] if t['id']==track['source_track_id']),None)
            if not source or fingerprint(source['cues'])!=track.get('source_hash'):
                raise HTTPException(409,'Nguồn đã thay đổi; cần dịch lại trước khi duyệt.')
        track['reviewed']=body.reviewed;store.save(db,doc)
    return doc
