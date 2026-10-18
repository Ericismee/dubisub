import hashlib
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import langcodes
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from . import store
from .subtitles import parse, validate, export


@asynccontextmanager
async def lifespan(app):
    store.migrate()
    yield


app = FastAPI(title='DubiSub', lifespan=lifespan)
from .workflows import router as workflow_router
app.include_router(workflow_router)
from .voices import router as voices_router
app.include_router(voices_router)
from .dubbing import router as dubbing_router
app.include_router(dubbing_router)


@app.middleware('http')
async def local_requests(request, call_next):
    # Browser clients may mutate only from the local UI/API origins.
    origin = request.headers.get('origin')
    allowed = {'http://127.0.0.1:3600', 'http://localhost:3600', 'http://127.0.0.1:6060', 'http://localhost:6060'}
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in allowed:
        return Response('Untrusted browser origin', status_code=403)
    if request.url.path.endswith('/upload'):
        length = request.headers.get('content-length')
        if not length or not length.isdigit():
            return Response('Upload requires Content-Length', status_code=411)
        if int(length) > int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2 + 1024**2:
            return Response('Upload request exceeds limit', status_code=413)
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return Response('Resource not found', status_code=404)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return Response(str(exc), status_code=422)


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    mode: Literal['full', 'review'] = 'full'
    target_language: str = 'vi'

    @field_validator('name')
    @classmethod
    def project_name(cls, value):
        value=value.strip()
        if not value:raise ValueError('Tên dự án không được để trống.')
        return value

    @field_validator('target_language')
    @classmethod
    def language(cls, value):
        try:
            if not langcodes.tag_is_valid(value):
                raise ValueError('Invalid BCP 47 language')
            return langcodes.standardize_tag(value)
        except (ValueError, langcodes.LanguageTagError):
            raise ValueError('Invalid BCP 47 language')


class Cue(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    start_ms: int = Field(strict=True)
    end_ms: int = Field(strict=True)
    text: str = Field(max_length=10000)


class EditTrack(BaseModel):
    revision: int
    cues: list[Cue] = Field(max_length=20000)


@app.get('/health')
def health():
    with store.connect() as db:
        db.execute('SELECT 1')
    return {'status': 'ok', 'product': 'DubiSub', 'schema_version': 3}


class ProviderConfig(BaseModel):
    kind: Literal['asr', 'translation', 'tts']
    protocol: Literal['openai', 'ollama'] = 'openai'
    endpoint: str = Field(max_length=2048)
    model: str = Field(default='', max_length=160)
    key_env: str = Field(default='', pattern=r'^(DUBISUB_[A-Z0-9_]{1,80})?$')

    @field_validator('endpoint')
    @classmethod
    def endpoint_url(cls, value):
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Endpoint must be HTTP(S) with no credentials, query or fragment')
        return value.rstrip('/')


class SettingsEdit(BaseModel):
    providers: list[ProviderConfig] = Field(max_length=3)


@app.put('/api/settings')
def update_settings(body: SettingsEdit):
    if any(p.protocol=='ollama' and p.kind!='translation' for p in body.providers):
        raise HTTPException(422, 'Ollama protocol supports translation only')
    if len({p.kind for p in body.providers}) != len(body.providers):
        raise HTTPException(422, 'Only one configuration per provider kind')
    with store.connect() as db:
        db.execute('INSERT INTO settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET providers=excluded.providers',
                   (json.dumps([p.model_dump() for p in body.providers]),))
    return settings()


@app.get('/api/settings')
def settings():
    with store.connect() as db:
        row = db.execute('SELECT providers FROM settings WHERE id=1').fetchone()
    providers = json.loads(row[0]) if row else []
    from .providers import DEFAULT_TTS
    if not any(p['kind']=='tts' for p in providers):providers.append(dict(DEFAULT_TTS))
    providers = [dict(**p, verified=False, capabilities=[], key_present=bool(p['key_env'] and os.getenv(p['key_env']))) for p in providers]
    return {'max_upload_mb': int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')),
            'providers': providers, 'ai_status': 'unverified' if providers else 'not_configured',
            'ffmpeg_available': bool(shutil.which(os.getenv('DUBISUB_FFMPEG', 'ffmpeg'))),
            'ffprobe_available': bool(shutil.which(os.getenv('DUBISUB_FFPROBE', 'ffprobe')))}


@app.get('/api/project-library')
def project_library(offset:int=Query(0,ge=0),search:str=Query('',max_length=160)):
    with store.connect() as db:
        db.create_function('casefold',1,lambda value:str(value or '').casefold())
        rows=db.execute("""SELECT id,json_extract(document,'$.name') AS name,
            json_extract(document,'$.mode') AS mode,json_extract(document,'$.target_language') AS target_language,
            COALESCE(json_array_length(document,'$.tracks'),0) AS track_count
            FROM projects WHERE COALESCE(json_extract(document,'$.deleted'),0)=0
            AND instr(casefold(json_extract(document,'$.name')),casefold(?))>0
            ORDER BY rowid DESC LIMIT 25 OFFSET ?""",(search.strip(),offset)).fetchall()
    return {'items':[dict(r) for r in rows[:24]],'has_more':len(rows)>24}


@app.get('/api/projects')
def projects(deleted:bool=False):
    with store.connect() as db:
        rows = db.execute("SELECT document FROM projects WHERE COALESCE(json_extract(document,'$.deleted'),0)=? ORDER BY rowid DESC LIMIT 100",(int(deleted),)).fetchall()
    return [{k:v for k,v in json.loads(r[0]).items() if k != 'tracks'} for r in rows]


@app.post('/api/projects', status_code=201)
def create(body: CreateProject):
    document = dict(id=store.uid(), schema_version=1, revision=0, tracks=[], **body.model_dump())
    with store.connect() as db:
        db.execute('INSERT INTO projects VALUES (?,?)', (document['id'], json.dumps(document)))
    return document


class ProjectEdit(CreateProject):
    revision: int


class ProjectDelete(BaseModel):
    revision: int


@app.patch('/api/projects/{project_id}')
def update_project(project_id: str, body: ProjectEdit):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        doc=store.project(db,project_id)
        if doc['revision']!=body.revision:
            raise HTTPException(409,'Dự án đã thay đổi. Hãy mở lại trước khi sửa thông tin.')
        doc.update(body.model_dump(exclude={'revision'}))
        store.save(db,doc)
    return doc


@app.delete('/api/projects/{project_id}')
def delete_project(project_id: str, body: ProjectDelete):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        doc=store.project(db,project_id)
        if doc['revision']!=body.revision:
            raise HTTPException(409,'Dự án đã thay đổi. Hãy mở lại trước khi xóa.')
        doc['deleted']=True
        db.execute("UPDATE jobs SET state='canceled' WHERE project_id=? AND state IN ('queued','running')",(project_id,))
        store.save(db,doc)
    return {'id':project_id,'deleted':True,'can_restore':True}


@app.post('/api/projects/{project_id}/restore')
def restore_project(project_id: str):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT document FROM projects WHERE id=?',(project_id,)).fetchone()
        if not row:raise KeyError(project_id)
        doc=json.loads(row[0]);doc['deleted']=False;store.save(db,doc)
    return doc


@app.get('/api/projects/{project_id}')
def read(project_id: str):
    with store.connect() as db:
        document = store.project(db, project_id)
        from .ai_tasks import fingerprint
        for track in document['tracks']:
            if track.get('source_track_id'):
                source=next((t for t in document['tracks'] if t['id']==track['source_track_id']),None)
                track['source_changed']=not source or fingerprint(source['cues'])!=track.get('source_hash')
        document['assets'] = [dict(r) for r in db.execute(
            "SELECT id,filename,kind,checksum,metadata FROM assets WHERE project_id=? AND kind NOT IN ('remote','generated')", (project_id,))]
        document['jobs'] = [dict(r) for r in db.execute(
            'SELECT id,asset_id,kind,state,attempts,progress,error FROM jobs WHERE project_id=?', (project_id,))]
        document['links'] = [dict(r) for r in db.execute('SELECT link_imports.id,assets.filename FROM link_imports JOIN assets ON assets.id=link_imports.id WHERE assets.project_id=?',(project_id,))]
    return document


class LinkRequest(BaseModel):
    url: str = Field(min_length=8,max_length=8192)


class LinkSelection(BaseModel):
    mode: Literal['video','audio','subtitles'] = 'video'
    format_id: str = Field(default='',max_length=100)
    subtitle_ids: list[str] = Field(default_factory=list,max_length=5)


@app.post('/api/projects/{project_id}/links',status_code=202)
def inspect_link(project_id: str, body: LinkRequest):
    from .safe_http import SafeHTTP, redact
    from .link_sources import youtube_url
    # DNS resolution and all remote I/O happen only in the worker.
    parsed=urlsplit(body.url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422,'Chỉ nhận liên kết HTTP(S) không chứa thông tin đăng nhập.')
    canonical=youtube_url(body.url)
    aid,jid=store.uid(),store.uid()
    with store.connect() as db:
        store.project(db,project_id)
        db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,NULL)',(aid,project_id,redact(body.url),'','remote',''))
        db.execute('INSERT INTO link_imports VALUES(?,?,NULL)',(aid,canonical or body.url))
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind) VALUES(?,?,?,'inspect_link')",(jid,project_id,aid))
    return {'link_id':aid,'job_id':jid}


@app.get('/api/links/{link_id}')
def link_info(link_id: str):
    from .link_sources import public_info
    with store.connect() as db:
        row=db.execute('SELECT link_imports.*,assets.project_id FROM link_imports JOIN assets ON assets.id=link_imports.id WHERE link_imports.id=?',(link_id,)).fetchone()
        if not row:raise KeyError(link_id)
        store.project(db,row['project_id'])
        jobs=[dict(r) for r in db.execute('SELECT id,kind,state,progress,error,attempts,checkpoint FROM jobs WHERE asset_id=? ORDER BY rowid DESC',(link_id,))]
    for job in jobs:
        raw=job.pop('checkpoint')
        try:status=json.loads(raw) if raw and job['kind']=='download_link' else {}
        except ValueError:status={}
        job['transfer']={k:status[k] for k in ('downloaded_bytes','total_bytes','file_index','file_count','bytes_per_second') if k in status} if isinstance(status,dict) else {}
    return {'id':link_id,'info':public_info(json.loads(row['inspection'])) if row['inspection'] else None,'jobs':jobs}


@app.get('/api/links/{link_id}/thumbnail')
def thumbnail(link_id:str):
    link_info(link_id)
    path=store.root()/'link-thumbnails'/link_id
    if not path.is_file():raise KeyError(link_id)
    with path.open('rb') as f:header=f.read(12)
    mime='image/png' if header.startswith(b'\x89PNG') else 'image/webp' if header.startswith(b'RIFF') else 'image/jpeg'
    return FileResponse(path,media_type=mime,headers={'X-Content-Type-Options':'nosniff'})


@app.post('/api/links/{link_id}/download',status_code=202)
def import_link(link_id: str, body: LinkSelection):
    from .link_tasks import download_plan
    jid=store.uid()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT link_imports.*,assets.project_id FROM link_imports JOIN assets ON assets.id=link_imports.id WHERE link_imports.id=?',(link_id,)).fetchone()
        if not row:raise KeyError(link_id)
        store.project(db,row['project_id'])
        if not row['inspection']:raise HTTPException(409,'Chờ phân tích nguồn hoàn tất.')
        download_plan(json.loads(row['inspection']),body.model_dump())
        if db.execute("SELECT id FROM jobs WHERE asset_id=? AND kind='download_link' AND state IN ('queued','running','succeeded')",(link_id,)).fetchone():
            raise HTTPException(409,'Nguồn này đã nhập hoặc đang nhập. Phân tích lại link để nhập lựa chọn khác.')
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'download_link',?)",(jid,row['project_id'],link_id,json.dumps(body.model_dump())))
    return {'job_id':jid}


@app.post('/api/projects/{project_id}/upload', status_code=202)
async def upload(project_id: str, file: UploadFile = File(), kind: Literal['media', 'subtitle'] = Form()):
    with store.connect() as db:
        store.project(db, project_id)
    extension = Path(file.filename or '').suffix.lower().lstrip('.')
    if kind == 'subtitle' and extension not in ('srt', 'vtt', 'ass'):
        raise HTTPException(422, 'Choose SRT, VTT or ASS')
    asset_id = store.uid()
    directory = store.root() / 'assets'
    directory.mkdir(exist_ok=True)
    path = directory / asset_id  # Never use an untrusted filename as a filesystem path.
    cap = min(8 * 1024 * 1024, int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2) if kind == 'subtitle' else int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open('xb') as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > cap or shutil.disk_usage(directory).free < len(chunk) + 64 * 1024**2:
                    raise HTTPException(413, 'Upload limit or free disk reserve exceeded')
                digest.update(chunk)
                await run_in_threadpool(output.write, chunk)
        if not size:
            raise HTTPException(422, 'Empty file')
        cues = await run_in_threadpool(parse, path.read_text(encoding='utf-8-sig'), extension) if kind == 'subtitle' else None
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            doc = store.project(db, project_id)
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,NULL)',
                       (asset_id, project_id, (file.filename or 'upload')[:255], str(path), kind, digest.hexdigest()))
            if cues is not None:
                doc['tracks'].append(dict(id=store.uid(), asset_id=asset_id, language='und', cues=cues))
                store.save(db, doc)
            else:
                db.execute('INSERT INTO jobs(id,project_id,asset_id,kind) VALUES (?,?,?,?)',
                           (store.uid(), project_id, asset_id, 'probe'))
        return {'asset_id': asset_id}
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.put('/api/projects/{project_id}/tracks/{track_id}')
def edit(project_id: str, track_id: str, body: EditTrack):
    cues = [c.model_dump() for c in body.cues]
    validate(cues)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        doc = store.project(db, project_id)
        if doc['revision'] != body.revision:
            raise HTTPException(409, 'Project changed elsewhere; reopen before saving')
        track = next((t for t in doc['tracks'] if t['id'] == track_id), None)
        if track is None:
            raise KeyError(track_id)
        track['cues'] = cues
        track['reviewed'] = False
        store.save(db, doc)
    return doc


@app.get('/api/projects/{project_id}/tracks/{track_id}/export')
def download(project_id: str, track_id: str, format: Literal['srt', 'vtt', 'ass'] = 'srt'):
    with store.connect() as db:
        doc = store.project(db, project_id)
    track = next((t for t in doc['tracks'] if t['id'] == track_id), None)
    if track is None:
        raise KeyError(track_id)
    return Response(export(track['cues'], format), media_type='text/vtt; charset=utf-8' if format == 'vtt' else 'text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="subtitles.{format}"'})


@app.get('/api/projects/{project_id}/assets/{asset_id}/content')
def media(project_id: str, asset_id: str):
    with store.connect() as db:
        store.project(db,project_id)
        row = db.execute('SELECT * FROM assets WHERE id=? AND project_id=? AND kind="media"',
                         (asset_id, project_id)).fetchone()
    if row is None:
        raise KeyError(asset_id)
    metadata = json.loads(row['metadata']) if row['metadata'] else {}
    fmt = metadata.get('format', {}).get('format_name', '')
    mime = 'video/webm' if 'webm' in fmt else ('video/mp4' if 'mov' in fmt else 'application/octet-stream')
    return FileResponse(row['path'], media_type=mime, filename=row['filename'], content_disposition_type='inline')


@app.post('/api/jobs/{job_id}/{action}')
def control(job_id: str, action: Literal['cancel', 'retry']):
    with store.connect() as db:
        row=db.execute('SELECT project_id FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not row:raise KeyError(job_id)
        store.project(db,row['project_id'])
        if action == 'cancel':
            result = db.execute("UPDATE jobs SET state='canceled' WHERE id=? AND state IN ('queued','running')", (job_id,))
        else:
            result = db.execute("UPDATE jobs SET state='queued',error=NULL,progress=0 WHERE id=? AND state IN ('failed','canceled') AND attempts<3", (job_id,))
        if not result.rowcount:
            raise HTTPException(409, 'Job missing, not eligible, or retry limit reached')
    return {'status': action}


@app.get('/api/projects/{project_id}/artifacts/{artifact_id}')
def artifact(project_id:str,artifact_id:str):
    with store.connect() as db:doc=store.project(db,project_id)
    item=next((a for a in doc.get('artifacts',[]) if a['id']==artifact_id),None)
    if not item:raise KeyError(artifact_id)
    path=store.root()/'artifacts'/f'{item["job_id"]}.mp4'
    if not path.is_file():raise KeyError(artifact_id)
    return FileResponse(path,media_type='video/mp4',filename=item['filename'])
